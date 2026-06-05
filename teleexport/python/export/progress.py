"""Export progress tracking and event emission."""
from typing import Callable, Optional


class ExportProgress:
    """Tracks and emits progress events during export."""

    def __init__(self, callback: Optional[Callable] = None):
        self._callback = callback
        self._export_id: str | None = None

    def set_export_id(self, export_id: str):
        """Set the current export ID."""
        self._export_id = export_id

    def update_chat(
        self,
        chat_id: int,
        chat_name: str,
        messages_done: int,
        messages_total: int,
    ):
        """Emit chat progress event."""
        if not self._callback:
            return

        percent = (messages_done / messages_total * 100) if messages_total > 0 else 0

        self._callback(
            "export.progress",
            {
                "export_id": self._export_id,
                "chat_id": chat_id,
                "chat_name": chat_name,
                "percent": round(percent, 1),
                "messages_done": messages_done,
                "messages_total": messages_total,
            },
        )

    def update_media(
        self,
        file_name: str,
        downloaded_bytes: int,
        total_bytes: int,
    ):
        """Emit media download progress event."""
        if not self._callback:
            return

        percent = (
            (downloaded_bytes / total_bytes * 100) if total_bytes > 0 else 0
        )

        self._callback(
            "export.media_progress",
            {
                "export_id": self._export_id,
                "file_name": file_name,
                "percent": round(percent, 1),
                "downloaded_bytes": downloaded_bytes,
                "total_bytes": total_bytes,
            },
        )

    def chat_complete(self, chat_id: int, messages_exported: int, media_count: int):
        """Emit chat complete event."""
        if not self._callback:
            return

        self._callback(
            "export.chat_complete",
            {
                "export_id": self._export_id,
                "chat_id": chat_id,
                "messages_exported": messages_exported,
                "media_count": media_count,
            },
        )

    def export_error(self, chat_id: int, error_message: str, recoverable: bool = True):
        """Emit export error event."""
        if not self._callback:
            return

        self._callback(
            "export.error",
            {
                "export_id": self._export_id,
                "chat_id": chat_id,
                "error_message": error_message,
                "recoverable": recoverable,
            },
        )
