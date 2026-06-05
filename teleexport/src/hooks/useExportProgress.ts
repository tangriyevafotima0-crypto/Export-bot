import { useCallback, useEffect } from 'react';
import { useExportStore } from '@/stores/export.store';
import type { ExportProgress, ExportResult, ExportError } from '@/types/export.types';

export function useExportProgress() {
  const updateProgress = useExportStore((s) => s.updateProgress);
  const setCompleted = useExportStore((s) => s.setCompleted);
  const setError = useExportStore((s) => s.setError);

  const handleProgress = useCallback((data: unknown) => {
    updateProgress(data as ExportProgress);
  }, [updateProgress]);

  const handleComplete = useCallback((data: unknown) => {
    setCompleted(data as ExportResult);
  }, [setCompleted]);

  const handleError = useCallback((data: unknown) => {
    setError(data as ExportError);
  }, [setError]);

  useEffect(() => {
    window.teleexport.python.onEvent('export.progress', handleProgress);
    window.teleexport.python.onEvent('export.complete', handleComplete);
    window.teleexport.python.onEvent('export.error', handleError);
    return () => {
      window.teleexport.python.offEvent('export.progress', handleProgress);
      window.teleexport.python.offEvent('export.complete', handleComplete);
      window.teleexport.python.offEvent('export.error', handleError);
    };
  }, [handleProgress, handleComplete, handleError]);
}
