interface DateRangePickerProps {
  dateFrom: string | null;
  dateTo: string | null;
  onDateFromChange: (date: string | null) => void;
  onDateToChange: (date: string | null) => void;
}

export function DateRangePicker({ dateFrom, dateTo, onDateFromChange, onDateToChange }: DateRangePickerProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-slate-300">Date Range (optional)</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">From</label>
          <input
            type="date"
            value={dateFrom ?? ''}
            onChange={(e) => onDateFromChange(e.target.value || null)}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">To</label>
          <input
            type="date"
            value={dateTo ?? ''}
            onChange={(e) => onDateToChange(e.target.value || null)}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>
    </div>
  );
}
