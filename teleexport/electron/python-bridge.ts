import { ChildProcess, spawn } from 'child_process';
import { EventEmitter } from 'events';
import path from 'path';

interface PendingCall {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

export class PythonBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private pendingCalls: Map<string, PendingCall> = new Map();
  private callId = 0;
  private buffer = '';
  private pythonPath: string;

  constructor() {
    super();
    const isDev = process.env.NODE_ENV === 'development';
    if (isDev) {
      this.pythonPath = path.join(__dirname, '..', 'python', 'main.py');
    } else {
      this.pythonPath = path.join(process.resourcesPath, 'python', 'main.py');
    }
  }

  start(): void {
    this.process = spawn('python', [this.pythonPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });

    this.process.stdout?.on('data', (data: Buffer) => {
      this.buffer += data.toString();
      this.processBuffer();
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error('[Python stderr]:', data.toString());
    });

    this.process.on('close', (code) => {
      console.log(`[PythonBridge] Process exited with code ${code}`);
      this.emit('closed', code);
      this.rejectAllPending('Python process exited');
    });

    this.process.on('error', (err) => {
      console.error('[PythonBridge] Process error:', err);
      this.emit('error', err);
    });
  }

  async call(method: string, params: Record<string, unknown> = {}, timeout = 30000): Promise<unknown> {
    if (!this.process || !this.process.stdin) {
      throw new Error('Python process is not running');
    }

    const id = String(++this.callId);
    const message = JSON.stringify({ id, method, params }) + '\n';

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingCalls.delete(id);
        reject(new Error(`RPC call "${method}" timed out after ${timeout}ms`));
      }, timeout);

      this.pendingCalls.set(id, { resolve, reject, timer });
      this.process!.stdin!.write(message);
    });
  }

  stop(): void {
    if (this.process) {
      this.process.kill('SIGTERM');
      this.process = null;
    }
    this.rejectAllPending('Bridge stopped');
  }

  private processBuffer(): void {
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const message = JSON.parse(line);
        this.handleMessage(message);
      } catch {
        console.error('[PythonBridge] Failed to parse:', line);
      }
    }
  }

  private handleMessage(message: { id: string | null; result?: unknown; error?: { code: number; message: string }; event?: string; data?: unknown }): void {
    if (message.id === null && message.event) {
      this.emit('event', message.event, message.data);
      return;
    }

    if (message.id) {
      const pending = this.pendingCalls.get(message.id);
      if (!pending) return;

      clearTimeout(pending.timer);
      this.pendingCalls.delete(message.id);

      if (message.error) {
        pending.reject(new Error(message.error.message));
      } else {
        pending.resolve(message.result);
      }
    }
  }

  private rejectAllPending(reason: string): void {
    for (const [id, pending] of this.pendingCalls.entries()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(reason));
      this.pendingCalls.delete(id);
    }
  }
}
