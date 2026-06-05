import { create } from 'zustand';
import type { ExportConfig, ExportProgress, ExportStatus, ExportResult, ExportError } from '@/types/export.types';
import type { MediaType } from '@/types/chat.types';

interface ChatProgress {
  chatId: number;
  chatName: string;
  percent: number;
  messagesDone: number;
  messagesTotal: number;
}

interface ExportState {
  config: ExportConfig;
  status: ExportStatus;
  exportId: string | null;
  chatProgress: Record<number, ChatProgress>;
  overallPercent: number;
  result: ExportResult | null;
  error: ExportError | null;

  setConfig: (config: Partial<ExportConfig>) => void;
  startExport: () => Promise<void>;
  cancelExport: () => Promise<void>;
  updateProgress: (progress: ExportProgress) => void;
  setCompleted: (result: ExportResult) => void;
  setError: (error: ExportError) => void;
  reset: () => void;
}

const defaultConfig: ExportConfig = {
  chatIds: [],
  format: 'html',
  dateFrom: null,
  dateTo: null,
  mediaTypes: ['photo', 'video', 'audio', 'document', 'voice', 'sticker', 'animation', 'video_note'] as MediaType[],
  outputDir: '',
  includeReplies: true,
  includeForwards: true,
  maxFileSizeMb: 500,
};

export const useExportStore = create<ExportState>((set, get) => ({
  config: { ...defaultConfig },
  status: 'idle',
  exportId: null,
  chatProgress: {},
  overallPercent: 0,
  result: null,
  error: null,

  setConfig: (partial) => {
    set((state) => ({ config: { ...state.config, ...partial } }));
  },

  startExport: async () => {
    const { config } = get();
    set({ status: 'running', chatProgress: {}, overallPercent: 0, result: null, error: null });
    try {
      const result = await window.teleexport.python.call('export.start', {
        chat_ids: config.chatIds,
        format: config.format,
        date_from: config.dateFrom,
        date_to: config.dateTo,
        media_types: config.mediaTypes,
        output_dir: config.outputDir,
        include_replies: config.includeReplies,
        include_forwards: config.includeForwards,
        max_file_size_mb: config.maxFileSizeMb,
      }) as { export_id: string };
      set({ exportId: result.export_id });
    } catch (err) {
      set({ status: 'error', error: { chatId: 0, errorMessage: (err as Error).message, recoverable: false } });
    }
  },

  cancelExport: async () => {
    const { exportId } = get();
    if (!exportId) return;
    try {
      await window.teleexport.python.call('export.cancel', { export_id: exportId });
      set({ status: 'cancelled' });
    } catch (err) {
      set({ error: { chatId: 0, errorMessage: (err as Error).message, recoverable: false } });
    }
  },

  updateProgress: (progress: ExportProgress) => {
    set((state) => {
      const chatProgress = {
        ...state.chatProgress,
        [progress.chatId]: {
          chatId: progress.chatId,
          chatName: progress.chatName,
          percent: progress.percent,
          messagesDone: progress.messagesDone,
          messagesTotal: progress.messagesTotal,
        },
      };
      const entries = Object.values(chatProgress);
      const overallPercent = entries.length > 0
        ? entries.reduce((sum, p) => sum + p.percent, 0) / entries.length
        : 0;
      return { chatProgress, overallPercent };
    });
  },

  setCompleted: (result: ExportResult) => {
    set({ status: 'completed', result, overallPercent: 100 });
  },

  setError: (error: ExportError) => {
    set({ status: 'error', error });
  },

  reset: () => {
    set({
      config: { ...defaultConfig },
      status: 'idle',
      exportId: null,
      chatProgress: {},
      overallPercent: 0,
      result: null,
      error: null,
    });
  },
}));
