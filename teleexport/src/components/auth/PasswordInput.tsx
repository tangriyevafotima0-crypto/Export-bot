import { useState } from 'react';
import { Lock } from 'lucide-react';
import { Button } from '@/components/shared/Button';

interface PasswordInputProps {
  onSubmit: (password: string) => void;
  loading: boolean;
  error: string | null;
}

export function PasswordInput({ onSubmit, loading, error }: PasswordInputProps) {
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password.trim()) {
      onSubmit(password);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="text-center mb-6">
        <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <Lock className="w-8 h-8 text-blue-400" />
        </div>
        <h2 className="text-xl font-semibold text-slate-100">Two-Factor Auth</h2>
        <p className="text-sm text-slate-400 mt-1">Enter your 2FA password</p>
      </div>

      <div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          autoFocus
        />
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      <Button type="submit" loading={loading} className="w-full" disabled={!password}>
        Submit
      </Button>
    </form>
  );
}
