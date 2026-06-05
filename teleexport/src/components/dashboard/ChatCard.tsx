import { Badge } from '@/components/shared/Badge';
import type { Chat, ChatType } from '@/types/chat.types';

interface ChatCardProps {
  chat: Chat;
  onClick?: (chat: Chat) => void;
}

const typeVariant: Record<ChatType, 'info' | 'success' | 'warning' | 'default'> = {
  private: 'info',
  group: 'success',
  supergroup: 'success',
  channel: 'warning',
};

export function ChatCard({ chat, onClick }: ChatCardProps) {
  return (
    <div
      onClick={() => onClick?.(chat)}
      className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-700/50 cursor-pointer transition-colors"
    >
      <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-sm font-medium text-slate-300 flex-shrink-0">
        {chat.name.charAt(0).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-100 truncate">{chat.name}</span>
          <Badge variant={typeVariant[chat.type]}>{chat.type}</Badge>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">
          {chat.messageCount.toLocaleString()} messages
        </p>
      </div>
    </div>
  );
}
