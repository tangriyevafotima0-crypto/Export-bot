import { useEffect } from 'react';
import { useChatsStore } from '@/stores/chats.store';

export function useChats() {
  const loadChats = useChatsStore((s) => s.loadChats);
  const searchChats = useChatsStore((s) => s.searchChats);
  const chats = useChatsStore((s) => s.filteredChats);
  const loading = useChatsStore((s) => s.loading);
  const error = useChatsStore((s) => s.error);
  const total = useChatsStore((s) => s.total);

  useEffect(() => {
    loadChats();
  }, [loadChats]);

  return { chats, loading, error, total, searchChats, loadChats };
}
