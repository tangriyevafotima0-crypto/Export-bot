import { useState } from 'react';
import { useChats } from '@/hooks/useChats';
import { useExportStore } from '@/stores/export.store';
import { Button } from '@/components/shared/Button';
import { ChatSelector } from './ChatSelector';
import { FormatSelector } from './FormatSelector';
import { DateRangePicker } from './DateRangePicker';
import { MediaOptions } from './MediaOptions';
import { ExportProgress as ExportProgressView } from './ExportProgress';

type WizardStep = 'select' | 'config' | 'progress';

export function ExportWizard() {
  const [step, setStep] = useState<WizardStep>('select');
  const { chats } = useChats();
  const { config, status, setConfig, startExport } = useExportStore();

  const handleStart = async () => {
    setStep('progress');
    await startExport();
  };

  const handleSelectDir = async () => {
    const dir = await window.teleexport.dialog.selectDirectory();
    if (dir) {
      setConfig({ outputDir: dir });
    }
  };

  if (step === 'progress' || status === 'running') {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-100">Export</h1>
        <ExportProgressView />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Export Wizard</h1>
        <p className="text-sm text-slate-400 mt-1">
          {step === 'select' ? 'Select chats to export' : 'Configure export options'}
        </p>
      </div>

      {step === 'select' && (
        <div className="space-y-4">
          <ChatSelector
            chats={chats}
            selectedIds={config.chatIds}
            onSelectionChange={(ids) => setConfig({ chatIds: ids })}
          />
          <Button
            onClick={() => setStep('config')}
            disabled={config.chatIds.length === 0}
            className="w-full"
          >
            Next: Configure Export
          </Button>
        </div>
      )}

      {step === 'config' && (
        <div className="space-y-6">
          <FormatSelector
            value={config.format}
            onChange={(format) => setConfig({ format })}
          />

          <DateRangePicker
            dateFrom={config.dateFrom}
            dateTo={config.dateTo}
            onDateFromChange={(dateFrom) => setConfig({ dateFrom })}
            onDateToChange={(dateTo) => setConfig({ dateTo })}
          />

          <MediaOptions
            selected={config.mediaTypes}
            onChange={(mediaTypes) => setConfig({ mediaTypes })}
          />

          <div className="space-y-2">
            <h3 className="text-sm font-medium text-slate-300">Output Directory</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={config.outputDir}
                readOnly
                placeholder="Select output directory..."
                className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm"
              />
              <Button variant="secondary" onClick={handleSelectDir}>
                Browse
              </Button>
            </div>
          </div>

          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setStep('select')} className="flex-1">
              Back
            </Button>
            <Button
              onClick={handleStart}
              disabled={!config.outputDir}
              className="flex-1"
            >
              Start Export
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
