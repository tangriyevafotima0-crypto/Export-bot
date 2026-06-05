export type ChatType = 'private' | 'group' | 'supergroup' | 'channel';

export type MediaType =
  | 'photo'
  | 'video'
  | 'audio'
  | 'document'
  | 'voice'
  | 'sticker'
  | 'animation'
  | 'video_note';

export interface Chat {
  id: number;
  name: string;
  type: ChatType;
  messageCount: number;
  lastMessageDate: string | null;
  avatarUrl?: string | null;
  unreadCount: number;
  isPinned?: boolean;
  isArchived?: boolean;
}

export interface ChatDetailed extends Chat {
  description: string | null;
  memberCount: number | null;
  mediaCount: number;
  createdAt: string | null;
  username: string | null;
}

export interface Message {
  id: number;
  chatId: number;
  senderId: number | null;
  senderName: string;
  text: string;
  date: string;
  mediaType: MediaType | null;
  mediaPath: string | null;
  replyToId: number | null;
  forwardedFrom: string | null;
}
