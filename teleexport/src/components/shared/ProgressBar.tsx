interface ProgressBarProps {
  percent: number;
  label?: string;
  className?: string;
}

export function ProgressBar({ percent, label, className = '' }: ProgressBarProps) {
  const clampedPercent = Math.min(100, Math.max(0, percent));

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <div className="flex justify-between text-sm text-slate-400 mb-1">
          <span>{label}</span>
          <span>{clampedPercent.toFixed(1)}%</span>
        </div>
      )}
      <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${clampedPercent}%` }}
        />
      </div>
    </div>
  );
}
