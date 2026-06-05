import { create } from 'zustand';

export type AuthStep = 'idle' | 'phone' | 'code' | 'password' | 'done';

interface User {
  id: number;
  firstName: string;
  lastName: string | null;
  phone: string;
  username: string | null;
}

interface AuthState {
  user: User | null;
  isLoggedIn: boolean;
  authStep: AuthStep;
  phone: string;
  phoneCodeHash: string;
  error: string | null;
  loading: boolean;

  checkSession: () => Promise<void>;
  sendCode: (phone: string, apiId?: string, apiHash?: string) => Promise<void>;
  verifyCode: (code: string) => Promise<void>;
  verifyPassword: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoggedIn: false,
  authStep: 'phone',
  phone: '',
  phoneCodeHash: '',
  error: null,
  loading: false,

  checkSession: async () => {
    set({ loading: true, error: null });
    try {
      const result = await window.teleexport.python.call('auth.check_session') as {
        has_session: boolean;
        user?: User;
      };
      if (result.has_session && result.user) {
        set({ isLoggedIn: true, user: result.user, authStep: 'done' });
      } else {
        set({ authStep: 'phone' });
      }
    } catch (err) {
      set({ error: (err as Error).message, authStep: 'phone' });
    } finally {
      set({ loading: false });
    }
  },

  sendCode: async (phone: string, apiId?: string, apiHash?: string) => {
    set({ loading: true, error: null });
    try {
      if (!apiId || !apiHash) {
        set({ error: 'API ID and API Hash are required' });
        return;
      }
      const result = await window.teleexport.python.call('auth.send_code', {
        phone,
        api_id: parseInt(apiId, 10),
        api_hash: apiHash,
      }) as {
        phone_code_hash: string;
      };
      set({ phone, phoneCodeHash: result.phone_code_hash, authStep: 'code' });
    } catch (err) {
      set({ error: (err as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  verifyCode: async (code: string) => {
    const { phone, phoneCodeHash } = get();
    set({ loading: true, error: null });
    try {
      const result = await window.teleexport.python.call('auth.sign_in', {
        phone,
        code,
        phone_code_hash: phoneCodeHash,
      }) as { success: boolean; user?: User; requires_2fa?: boolean };

      if (result.requires_2fa) {
        set({ authStep: 'password' });
      } else if (result.success && result.user) {
        set({ isLoggedIn: true, user: result.user, authStep: 'done' });
      }
    } catch (err) {
      const message = (err as Error).message;
      if (message.includes('2FA') || message.includes('password')) {
        set({ authStep: 'password' });
      } else {
        set({ error: message });
      }
    } finally {
      set({ loading: false });
    }
  },

  verifyPassword: async (password: string) => {
    set({ loading: true, error: null });
    try {
      const result = await window.teleexport.python.call('auth.sign_in_2fa', {
        password,
      }) as { success: boolean; user?: User };
      if (result.success) {
        set({ isLoggedIn: true, user: result.user ?? null, authStep: 'done' });
      }
    } catch (err) {
      set({ error: (err as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  logout: async () => {
    set({ loading: true, error: null });
    try {
      await window.teleexport.python.call('auth.logout');
      set({ isLoggedIn: false, user: null, authStep: 'phone', phone: '', phoneCodeHash: '' });
    } catch (err) {
      set({ error: (err as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  setError: (error) => set({ error }),
  reset: () => set({ user: null, isLoggedIn: false, authStep: 'phone', phone: '', phoneCodeHash: '', error: null, loading: false }),
}));
