import { Minus, Square, X } from 'lucide-react';

export function TitleBar() {
  const handleMinimize = () => window.teleexport?.window.minimize();
  const handleMaximize = () => window.teleexport?.window.maximize();
  const handleClose = () => window.teleexport?.window.close();

  return (
    <div className="h-8 bg-slate-900 flex items-center justify-between select-none drag-region border-b border-slate-800">
      <div className="flex items-center px-3 gap-2">
        <span className="text-sm font-medium text-slate-400">TeleExport</span>
      </div>
      <div className="flex no-drag">
        <button
          onClick={handleMinimize}
          className="px-3 h-8 flex items-center hover:bg-slate-700 transition-colors"
        >
          <Minus className="w-3.5 h-3.5 text-slate-400" />
        </button>
        <button
          onClick={handleMaximize}
          className="px-3 h-8 flex items-center hover:bg-slate-700 transition-colors"
        >
          <Square className="w-3 h-3 text-slate-400" />
        </button>
        <button
          onClick={handleClose}
          className="px-3 h-8 flex items-center hover:bg-red-500 transition-colors"
        >
          <X className="w-3.5 h-3.5 text-slate-400" />
        </button>
      </div>
    </div>
  );
}
