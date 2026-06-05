import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth.store';
import { PhoneInput } from './PhoneInput';
import { CodeInput } from './CodeInput';
import { PasswordInput } from './PasswordInput';

export function AuthScreen() {
  const { authStep, phone, loading, error, checkSession, sendCode, verifyCode, verifyPassword } = useAuthStore();

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  return (
    <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-800/50 border border-slate-700 rounded-2xl p-8">
        {authStep === 'phone' && (
          <PhoneInput onSubmit={sendCode} loading={loading} error={error} />
        )}
        {authStep === 'code' && (
          <CodeInput onSubmit={verifyCode} loading={loading} error={error} phone={phone} />
        )}
        {authStep === 'password' && (
          <PasswordInput onSubmit={verifyPassword} loading={loading} error={error} />
        )}
      </div>
    </div>
  );
}
