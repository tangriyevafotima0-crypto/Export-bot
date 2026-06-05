import { useState } from 'react';
import { useChats } from '@/hooks/useChats';
import { SearchBar } from './SearchBar';
import { StatsOverview } from './StatsOverview';
import { ChatList } from './ChatList';

export function Dashboard() {
  const { chats, loading, searchChats } = useChats();
  const [search, setSearch] = useState('');

  const handleSearch = (value: string) => {
    setSearch(value);
    searchChats(value);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">Overview of your Telegram data</p>
      </div>

      <StatsOverview chats={chats} />

      <div className="space-y-4">
        <SearchBar value={search} onChange={handleSearch} />
        <ChatList chats={chats} loading={loading} />
      </div>
    </div>
  );
}
