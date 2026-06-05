import { useState } from 'react';
import { Phone } from 'lucide-react';
import { Button } from '@/components/shared/Button';

interface PhoneInputProps {
  onSubmit: (phone: string, apiId?: string, apiHash?: string) => void;
  loading: boolean;
  error: string | null;
}

export function PhoneInput({ onSubmit, loading, error }: PhoneInputProps) {
  const [phone, setPhone] = useState('');
  const [apiId, setApiId] = useState('');
  const [apiHash, setApiHash] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (phone.trim() && apiId.trim() && apiHash.trim()) {
      onSubmit(phone.trim(), apiId.trim(), apiHash.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="text-center mb-6">
        <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <Phone className="w-8 h-8 text-blue-400" />
        </div>
        <h2 className="text-xl font-semibold text-slate-100">Sign In</h2>
        <p className="text-sm text-slate-400 mt-1">Enter your Telegram API credentials and phone number</p>
      </div>

      <div className="space-y-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">API ID</label>
          <input
            type="text"
            value={apiId}
            onChange={(e) => setApiId(e.target.value)}
            placeholder="12345678"
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">API Hash</label>
          <input
            type="text"
            value={apiHash}
            onChange={(e) => setApiHash(e.target.value)}
            placeholder="0123456789abcdef0123456789abcdef"
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Phone Number</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1234567890"
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            autoFocus
          />
        </div>
        <p className="text-xs text-slate-500">
          Get your API credentials from{' '}
          <span className="text-blue-400">my.telegram.org</span>
        </p>
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      <Button type="submit" loading={loading} className="w-full">
        Send Code
      </Button>
    </form>
  );
}
