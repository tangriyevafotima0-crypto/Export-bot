import type { ExportFormat } from '@/types/export.types';

interface FormatSelectorProps {
  value: ExportFormat;
  onChange: (format: ExportFormat) => void;
}

const formats: { id: ExportFormat; label: string; description: string }[] = [
  { id: 'html', label: 'HTML', description: 'Beautiful, browsable export with media' },
  { id: 'json', label: 'JSON', description: 'Structured data for developers' },
  { id: 'csv', label: 'CSV', description: 'Spreadsheet-compatible format' },
];

export function FormatSelector({ value, onChange }: FormatSelectorProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-slate-300">Export Format</h3>
      <div className="grid grid-cols-2 gap-3">
        {formats.map((format) => (
          <label
            key={format.id}
            className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-colors ${
              value === format.id
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-slate-700 hover:border-slate-600'
            }`}
          >
            <input
              type="radio"
              name="format"
              value={format.id}
              checked={value === format.id}
              onChange={() => onChange(format.id)}
              className="sr-only"
            />
            <span className="text-sm font-medium text-slate-100">{format.label}</span>
            <span className="text-xs text-slate-400 mt-1">{format.description}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
