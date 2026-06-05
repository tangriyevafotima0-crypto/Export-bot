import { useEffect, useCallback } from 'react';

export function useIPCCall() {
  const call = useCallback(async <T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> => {
    return await window.teleexport.python.call(method, params) as T;
  }, []);

  return call;
}

export function useIPCEvent(event: string, handler: (data: unknown) => void) {
  useEffect(() => {
    window.teleexport.python.onEvent(event, handler);
    return () => {
      window.teleexport.python.offEvent(event, handler);
    };
  }, [event, handler]);
}
