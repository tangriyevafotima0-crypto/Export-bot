import { useExportStore } from '@/stores/export.store';
import { useExportProgress } from '@/hooks/useExportProgress';
import { ProgressBar } from '@/components/shared/ProgressBar';
import { Button } from '@/components/shared/Button';
import { CheckCircle, XCircle } from 'lucide-react';

export function ExportProgress() {
  useExportProgress();

  const { status, chatProgress, overallPercent, result, error, cancelExport, reset } = useExportStore();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-300">Export Progress</h3>
        {status === 'running' && (
          <Button variant="danger" onClick={cancelExport} className="text-xs px-3 py-1">
            Cancel
          </Button>
        )}
      </div>

      <ProgressBar percent={overallPercent} label="Overall Progress" />

      <div className="space-y-3 max-h-48 overflow-y-auto pr-1">
        {Object.values(chatProgress).map((cp) => (
          <div key={cp.chatId} className="space-y-1">
            <div className="flex justify-between text-xs text-slate-400">
              <span className="truncate">{cp.chatName}</span>
              <span>{cp.messagesDone}/{cp.messagesTotal}</span>
            </div>
            <ProgressBar percent={cp.percent} />
          </div>
        ))}
      </div>

      {status === 'completed' && result && (
        <div className="flex items-center gap-3 p-4 bg-green-900/20 border border-green-800 rounded-lg">
          <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
          <div>
            <p className="text-sm text-green-300 font-medium">Export Complete</p>
            <p className="text-xs text-green-400/70 mt-0.5">
              {result.totalChats} chats, {result.totalMessages.toLocaleString()} messages, {result.totalMedia} media files
            </p>
          </div>
        </div>
      )}

      {status === 'error' && error && (
        <div className="flex items-center gap-3 p-4 bg-red-900/20 border border-red-800 rounded-lg">
          <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <div>
            <p className="text-sm text-red-300 font-medium">Export Failed</p>
            <p className="text-xs text-red-400/70 mt-0.5">{error.errorMessage}</p>
          </div>
        </div>
      )}

      {(status === 'completed' || status === 'error' || status === 'cancelled') && (
        <Button variant="secondary" onClick={reset} className="w-full">
          Start New Export
        </Button>
      )}
    </div>
  );
}
