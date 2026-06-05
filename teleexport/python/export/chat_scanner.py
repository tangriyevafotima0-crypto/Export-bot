"""Chat scanner for listing all available dialogs."""
from telethon import TelegramClient


class ChatScanner:
    """Scans and lists all available chats/dialogs."""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def scan_all(self, limit: int = 100) -> list[dict]:
        """Scan all dialogs and return structured chat list."""
        chats = []

        async for dialog in self.client.iter_dialogs(limit=limit):
            entity = dialog.entity
            chat_type = self._get_type(entity)

            chat_info = {
                "id": dialog.id,
                "name": dialog.name or "Unknown",
                "type": chat_type,
                "unread_count": dialog.unread_count,
                "message_count": dialog.message.id if dialog.message else 0,
                "last_message_date": (
                    dialog.message.date.isoformat()
                    if dialog.message and dialog.message.date
                    else None
                ),
                "is_pinned": dialog.pinned,
                "is_archived": dialog.archived,
            }

            # Add extra info based on type
            if chat_type == "channel":
                chat_info["participants_count"] = getattr(
                    entity, "participants_count", None
                )
            elif chat_type == "group":
                chat_info["participants_count"] = getattr(
                    entity, "participants_count", None
                )
            elif chat_type == "private":
                chat_info["username"] = getattr(entity, "username", None)
                chat_info["phone"] = getattr(entity, "phone", None)

            chats.append(chat_info)

        return chats

    @staticmethod
    def _get_type(entity) -> str:
        """Determine the chat type from entity."""
        if hasattr(entity, "broadcast") and entity.broadcast:
            return "channel"
        if hasattr(entity, "megagroup") and entity.megagroup:
            return "group"
        if hasattr(entity, "gigagroup") and entity.gigagroup:
            return "group"
        if hasattr(entity, "title"):
            return "group"
        return "private"
