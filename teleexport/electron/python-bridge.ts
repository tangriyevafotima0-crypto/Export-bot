import { ChildProcess, spawn } from 'child_process';
import { EventEmitter } from 'events';
import path from 'path';

/**
 * Recursively converts all snake_case keys in an object to camelCase.
 */
function toCamelCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(toCamelCase);
  }
  if (obj !== null && typeof obj === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      const camelKey = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
      result[camelKey] = toCamelCase(value);
    }
    return result;
  }
  return obj;
}

/**
 * Recursively converts all camelCase keys in an object to snake_case.
 */
function toSnakeCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(toSnakeCase);
  }
  if (obj !== null && typeof obj === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      const snakeKey = key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
      result[snakeKey] = toSnakeCase(value);
    }
    return result;
  }
  return obj;
}

interface PendingCall {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

const MAX_RESTART_ATTEMPTS = 3;
const SHUTDOWN_TIMEOUT_MS = 5000;

export class PythonBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private pendingCalls: Map<string, PendingCall> = new Map();
  private callId = 0;
  private buffer = '';
  private pythonPath: string;
  private ready = false;
  private restartAttempts = 0;
  private stopping = false;

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
    this.stopping = false;
    this.ready = false;

    this.process = spawn('python', [this.pythonPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });

    this.process.stdout?.on('data', (data: Buffer) => {
      if (!this.ready) {
        this.ready = true;
        this.restartAttempts = 0;
        this.emit('ready');
      }
      this.buffer += data.toString();
      this.processBuffer();
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error('[Python stderr]:', data.toString());
    });

    this.process.on('close', (code) => {
      console.log(`[PythonBridge] Process exited with code ${code}`);
      this.ready = false;
      this.process = null;
      this.emit('closed', code);
      this.rejectAllPending('Python process exited');

      if (!this.stopping && code !== 0) {
        this.attemptRestart();
      }
    });

    this.process.on('error', (err) => {
      console.error('[PythonBridge] Process error:', err);
      this.ready = false;
      this.emit('error', err);
      this.rejectAllPending(`Python process error: ${err.message}`);
    });
  }

  private attemptRestart(): void {
    if (this.restartAttempts >= MAX_RESTART_ATTEMPTS) {
      this.emit('error', new Error(`Python process failed after ${MAX_RESTART_ATTEMPTS} restart attempts`));
      return;
    }

    this.restartAttempts++;
    const delay = Math.pow(2, this.restartAttempts) * 1000;
    this.emit('restarting', this.restartAttempts);

    setTimeout(() => {
      if (!this.stopping) {
        this.start();
      }
    }, delay);
  }

  restart(): void {
    this.restartAttempts = 0;
    if (this.process) {
      this.stopping = true;
      this.process.kill('SIGTERM');
      this.process = null;
    }
    this.rejectAllPending('Bridge restarting');
    this.stopping = false;
    this.start();
  }

  async call(method: string, params: Record<string, unknown> = {}, timeout = 30000): Promise<unknown> {
    if (!this.process || !this.process.stdin) {
      throw new Error('Python process is not running');
    }

    if (!this.ready) {
      throw new Error('Python process is not ready');
    }

    const id = String(++this.callId);
    const snakeParams = toSnakeCase(params) as Record<string, unknown>;
    const message = JSON.stringify({ id, method, params: snakeParams }) + '\n';

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
    this.stopping = true;

    if (this.process) {
      const proc = this.process;
      proc.kill('SIGTERM');

      const killTimer = setTimeout(() => {
        try {
          proc.kill('SIGKILL');
        } catch {
          // Process may have already exited
        }
      }, SHUTDOWN_TIMEOUT_MS);

      proc.on('close', () => {
        clearTimeout(killTimer);
      });

      this.process = null;
    }

    this.ready = false;
    this.rejectAllPending('Bridge stopped');
  }

  isReady(): boolean {
    return this.ready;
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
      this.emit('event', message.event, toCamelCase(message.data));
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
        pending.resolve(toCamelCase(message.result));
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
