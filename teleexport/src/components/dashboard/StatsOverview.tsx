import { MessageSquare, Users, Image } from 'lucide-react';
import type { Chat } from '@/types/chat.types';

interface StatsOverviewProps {
  chats: Chat[];
}

export function StatsOverview({ chats }: StatsOverviewProps) {
  const totalChats = chats.length;
  const totalMessages = chats.reduce((sum, c) => sum + c.messageCount, 0);
  const groups = chats.filter((c) => c.type === 'group' || c.type === 'supergroup').length;

  const stats = [
    { label: 'Total Chats', value: totalChats, icon: Users, color: 'text-blue-400' },
    { label: 'Messages', value: totalMessages.toLocaleString(), icon: MessageSquare, color: 'text-green-400' },
    { label: 'Groups', value: groups, icon: Image, color: 'text-purple-400' },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <div key={stat.label} className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg bg-slate-700/50 ${stat.color}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-100">{stat.value}</p>
                <p className="text-xs text-slate-400">{stat.label}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
