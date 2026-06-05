import type { MediaType } from '@/types/chat.types';

interface MediaOptionsProps {
  selected: MediaType[];
  onChange: (types: MediaType[]) => void;
}

const mediaTypes: { id: MediaType; label: string }[] = [
  { id: 'photo', label: 'Photos' },
  { id: 'video', label: 'Videos' },
  { id: 'audio', label: 'Audio' },
  { id: 'document', label: 'Documents' },
  { id: 'voice', label: 'Voice Messages' },
  { id: 'sticker', label: 'Stickers' },
  { id: 'animation', label: 'GIFs' },
  { id: 'video_note', label: 'Video Notes' },
];

export function MediaOptions({ selected, onChange }: MediaOptionsProps) {
  const toggle = (type: MediaType) => {
    if (selected.includes(type)) {
      onChange(selected.filter((t) => t !== type));
    } else {
      onChange([...selected, type]);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-slate-300">Media Types</h3>
      <div className="grid grid-cols-2 gap-2">
        {mediaTypes.map((type) => (
          <label
            key={type.id}
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-700/50 cursor-pointer"
          >
            <input
              type="checkbox"
              checked={selected.includes(type.id)}
              onChange={() => toggle(type.id)}
              className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
            <span className="text-sm text-slate-200">{type.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
