import type { MediaType } from './chat.types';

export type ExportFormat = 'html' | 'json' | 'csv' | 'pdf';

export type ExportStatus = 'idle' | 'running' | 'completed' | 'cancelled' | 'error';

export interface ExportConfig {
  chatIds: number[];
  format: ExportFormat;
  dateFrom: string | null;
  dateTo: string | null;
  mediaTypes: MediaType[];
  outputDir: string;
  includeReplies: boolean;
  includeForwards: boolean;
  maxFileSizeMb: number;
}

export interface ExportProgress {
  exportId: string;
  chatId: number;
  chatName: string;
  percent: number;
  messagesDone: number;
  messagesTotal: number;
}

export interface ExportResult {
  exportId: string;
  totalChats: number;
  totalMessages: number;
  totalMedia: number;
  outputPath: string;
}

export interface ExportError {
  chatId: number;
  errorMessage: string;
  recoverable: boolean;
}
