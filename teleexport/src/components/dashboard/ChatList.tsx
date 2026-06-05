import type { Chat } from '@/types/chat.types';
import { ChatCard } from './ChatCard';
import { Skeleton } from '@/components/shared/Skeleton';

interface ChatListProps {
  chats: Chat[];
  loading: boolean;
  onChatClick?: (chat: Chat) => void;
}

export function ChatList({ chats, loading, onChatClick }: ChatListProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (chats.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-slate-400">No chats found</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
      {chats.map((chat) => (
        <ChatCard key={chat.id} chat={chat} onClick={onChatClick} />
      ))}
    </div>
  );
}
