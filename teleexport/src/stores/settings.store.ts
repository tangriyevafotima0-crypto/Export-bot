import { create } from 'zustand';

export type Theme = 'dark' | 'light';

interface SettingsState {
  outputDir: string;
  theme: Theme;
  language: string;

  setOutputDir: (dir: string) => void;
  setTheme: (theme: Theme) => void;
  setLanguage: (lang: string) => void;
  loadSettings: () => Promise<void>;
  saveSettings: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  outputDir: '',
  theme: 'dark',
  language: 'en',

  setOutputDir: (dir) => set({ outputDir: dir }),
  setTheme: (theme) => set({ theme }),
  setLanguage: (lang) => set({ language: lang }),

  loadSettings: async () => {
    try {
      const result = await window.teleexport.python.call('settings.get') as {
        settings: { outputDir: string; theme: Theme; language: string };
      };
      set({
        outputDir: result.settings.outputDir,
        theme: result.settings.theme,
        language: result.settings.language,
      });
    } catch {
      // Use defaults
    }
  },

  saveSettings: async () => {
    const { outputDir, theme, language } = get();
    try {
      await window.teleexport.python.call('settings.set', {
        settings: { outputDir, theme, language },
      });
    } catch {
      // Silent fail
    }
  },
}));
