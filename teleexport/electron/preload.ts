import { contextBridge, ipcRenderer } from 'electron';

type EventCallback = (data: unknown) => void;

const eventListeners: Map<string, Set<EventCallback>> = new Map();

ipcRenderer.on('python:event', (_event, eventName: string, data: unknown) => {
  const listeners = eventListeners.get(eventName);
  if (listeners) {
    listeners.forEach((cb) => cb(data));
  }
});

contextBridge.exposeInMainWorld('teleexport', {
  python: {
    call: (method: string, params?: Record<string, unknown>) => {
      return ipcRenderer.invoke('python:call', method, params || {});
    },
    onEvent: (event: string, callback: EventCallback) => {
      if (!eventListeners.has(event)) {
        eventListeners.set(event, new Set());
      }
      eventListeners.get(event)!.add(callback);
    },
    offEvent: (event: string, callback: EventCallback) => {
      const listeners = eventListeners.get(event);
      if (listeners) {
        listeners.delete(callback);
      }
    },
  },
  dialog: {
    selectDirectory: () => ipcRenderer.invoke('dialog:selectDirectory'),
    openFile: (path: string) => ipcRenderer.invoke('dialog:openFile', path),
  },
  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
  },
  window: {
    minimize: () => ipcRenderer.send('window:minimize'),
    maximize: () => ipcRenderer.send('window:maximize'),
    close: () => ipcRenderer.send('window:close'),
  },
});
