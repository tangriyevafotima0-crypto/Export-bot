import { useState, useEffect } from 'react';
import { KeyRound } from 'lucide-react';
import { Button } from '@/components/shared/Button';

interface CodeInputProps {
  onSubmit: (code: string) => void;
  onResend: () => void;
  loading: boolean;
  error: string | null;
  phone: string;
}

const RESEND_COOLDOWN_SECONDS = 60;

export function CodeInput({ onSubmit, onResend, loading, error, phone }: CodeInputProps) {
  const [code, setCode] = useState('');
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS);

  // Countdown timer for the "resend via SMS" button.
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (code.trim().length >= 5) {
      onSubmit(code.trim());
    }
  };

  const handleResend = () => {
    if (cooldown > 0 || loading) return;
    onResend();
    setCooldown(RESEND_COOLDOWN_SECONDS);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="text-center mb-6">
        <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <KeyRound className="w-8 h-8 text-blue-400" />
        </div>
        <h2 className="text-xl font-semibold text-slate-100">Verification Code</h2>
        <p className="text-sm text-slate-400 mt-1">Code sent to {phone}</p>
      </div>

      <div>
        <input
          type="text"
          inputMode="numeric"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          maxLength={6}
          className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-center text-2xl tracking-widest placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          autoFocus
        />
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      <Button type="submit" loading={loading} className="w-full" disabled={code.length < 5}>
        Verify
      </Button>

      <div className="text-center">
        <button
          type="button"
          onClick={handleResend}
          disabled={cooldown > 0 || loading}
          className="text-sm text-blue-400 hover:text-blue-300 disabled:text-slate-500 disabled:cursor-not-allowed transition-colors"
        >
          {cooldown > 0
            ? `Resend code via SMS in ${cooldown}s`
            : 'Did not receive it? Resend code via SMS'}
        </button>
      </div>
    </form>
  );
}
