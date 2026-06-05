export interface RPCRequest {
  id: string;
  method: string;
  params: Record<string, unknown>;
}

export interface RPCResponse {
  id: string;
  result?: unknown;
  error?: { code: number; message: string };
}

export interface RPCEvent {
  id: null;
  event: string;
  data: unknown;
}

export type IPCMessage = RPCRequest | RPCResponse | RPCEvent;

export interface TeleExportAPI {
  python: {
    call: (method: string, params?: Record<string, unknown>) => Promise<unknown>;
    onEvent: (event: string, callback: (data: unknown) => void) => void;
    offEvent: (event: string, callback: (data: unknown) => void) => void;
  };
  dialog: {
    selectDirectory: () => Promise<string | null>;
    openFile: (path: string) => Promise<void>;
  };
  app: {
    getVersion: () => Promise<string>;
  };
  window: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
  };
}

declare global {
  interface Window {
    teleexport: TeleExportAPI;
  }
}

export {};
