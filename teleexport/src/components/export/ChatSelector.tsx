import { useState } from 'react';
import type { Chat } from '@/types/chat.types';
import { SearchBar } from '@/components/dashboard/SearchBar';

interface ChatSelectorProps {
  chats: Chat[];
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
}

export function ChatSelector({ chats, selectedIds, onSelectionChange }: ChatSelectorProps) {
  const [search, setSearch] = useState('');

  const filtered = search
    ? chats.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()))
    : chats;

  const toggleChat = (chatId: number) => {
    if (selectedIds.includes(chatId)) {
      onSelectionChange(selectedIds.filter((id) => id !== chatId));
    } else {
      onSelectionChange([...selectedIds, chatId]);
    }
  };

  const toggleAll = () => {
    if (selectedIds.length === filtered.length) {
      onSelectionChange([]);
    } else {
      onSelectionChange(filtered.map((c) => c.id));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-300">
          Select Chats ({selectedIds.length} selected)
        </h3>
        <button onClick={toggleAll} className="text-xs text-blue-400 hover:text-blue-300">
          {selectedIds.length === filtered.length ? 'Deselect All' : 'Select All'}
        </button>
      </div>

      <SearchBar value={search} onChange={setSearch} placeholder="Search chats to export..." />

      <div className="max-h-64 overflow-y-auto space-y-1 pr-1">
        {filtered.map((chat) => (
          <label
            key={chat.id}
            className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-700/50 cursor-pointer"
          >
            <input
              type="checkbox"
              checked={selectedIds.includes(chat.id)}
              onChange={() => toggleChat(chat.id)}
              className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
            <div className="flex-1 min-w-0">
              <span className="text-sm text-slate-200 truncate block">{chat.name}</span>
              <span className="text-xs text-slate-500">{chat.messageCount.toLocaleString()} messages</span>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
