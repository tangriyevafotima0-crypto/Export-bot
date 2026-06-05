import { create } from 'zustand';
import type { Chat, ChatDetailed } from '@/types/chat.types';

interface ChatsState {
  chats: Chat[];
  filteredChats: Chat[];
  selectedChat: ChatDetailed | null;
  searchQuery: string;
  loading: boolean;
  error: string | null;
  total: number;

  loadChats: (limit?: number, offset?: number) => Promise<void>;
  searchChats: (query: string) => void;
  getChatDetails: (chatId: number) => Promise<void>;
  clearSelection: () => void;
}

export const useChatsStore = create<ChatsState>((set, get) => ({
  chats: [],
  filteredChats: [],
  selectedChat: null,
  searchQuery: '',
  loading: false,
  error: null,
  total: 0,

  loadChats: async (limit = 100, offset = 0) => {
    set({ loading: true, error: null });
    try {
      const result = await window.teleexport.python.call('chats.list', {
        limit,
        offset,
      }) as { chats: Chat[]; total: number };
      set({ chats: result.chats, filteredChats: result.chats, total: result.total });
    } catch (err) {
      set({ error: (err as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  searchChats: (query: string) => {
    const { chats } = get();
    set({ searchQuery: query });
    if (!query.trim()) {
      set({ filteredChats: chats });
      return;
    }
    const lower = query.toLowerCase();
    const filtered = chats.filter((chat) =>
      chat.name.toLowerCase().includes(lower)
    );
    set({ filteredChats: filtered });
  },

  getChatDetails: async (chatId: number) => {
    set({ loading: true, error: null });
    try {
      const result = await window.teleexport.python.call('chats.get_details', {
        chatId,
      }) as { chat: ChatDetailed };
      set({ selectedChat: result.chat });
    } catch (err) {
      set({ error: (err as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  clearSelection: () => set({ selectedChat: null }),
}));
