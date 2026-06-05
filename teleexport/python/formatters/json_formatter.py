"""JSON formatter for streaming JSON export using orjson."""
from pathlib import Path
from datetime import datetime
from typing import Any

import orjson


class JSONFormatter:
    """Formats chat messages as streaming JSON."""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir

    def format(
        self,
        chat_name: str,
        entity,
        messages: list,
        media_dir: Path,
    ) -> Path:
        """Format messages as JSON file."""
        output_path = self.output_dir / f"{chat_name}.json"

        export_data = {
            "chat_name": chat_name,
            "chat_type": self._get_chat_type(entity),
            "export_date": datetime.now().isoformat(),
            "total_messages": len(messages),
            "messages": [self._message_to_dict(msg) for msg in messages],
        }

        output_path.write_bytes(
            orjson.dumps(export_data, option=orjson.OPT_INDENT_2)
        )

        return output_path

    def _message_to_dict(self, msg) -> dict[str, Any]:
        """Convert a message to a serializable dictionary."""
        data = {
            "id": msg.id,
            "date": msg.date.isoformat() if msg.date else None,
            "sender_id": getattr(msg, "sender_id", None),
            "sender_name": getattr(msg, "sender_name", None),
            "text": msg.text or "",
            "reply_to_msg_id": getattr(msg, "reply_to_msg_id", None),
        }

        # Forward info
        if getattr(msg, "fwd_from", None):
            data["forwarded"] = True
            data["fwd_from_name"] = getattr(msg.fwd_from, "from_name", None)
        else:
            data["forwarded"] = False

        # Media info
        media_type = self._get_media_type(msg)
        if media_type:
            data["media_type"] = media_type
            if msg.file:
                data["file_name"] = getattr(msg.file, "name", None)
                data["file_size"] = getattr(msg.file, "size", None)

        return data

    @staticmethod
    def _get_media_type(msg) -> str | None:
        """Determine media type."""
        if getattr(msg, "photo", None):
            return "photo"
        if getattr(msg, "video", None):
            return "video"
        if getattr(msg, "audio", None):
            return "audio"
        if getattr(msg, "voice", None):
            return "voice"
        if getattr(msg, "sticker", None):
            return "sticker"
        if getattr(msg, "document", None):
            return "document"
        return None

    @staticmethod
    def _get_chat_type(entity) -> str:
        """Determine chat type from entity."""
        if hasattr(entity, "broadcast") and entity.broadcast:
            return "channel"
        if hasattr(entity, "megagroup") and entity.megagroup:
            return "group"
        return "private"
