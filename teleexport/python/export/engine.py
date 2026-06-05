"""Main export engine orchestrating the full export process."""
import json
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional

from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
)

from ..core.client import TeleExportClient
from .message_fetcher import MessageFetcher
from .media_downloader import MediaDownloader
from .progress import ExportProgress
from ..formatters.html_formatter import HTMLFormatter
from ..formatters.json_formatter import JSONFormatter
from ..formatters.csv_formatter import CSVFormatter


@dataclass
class ExportConfig:
    """Configuration for an export operation."""

    chat_ids: list[int]
    output_dir: Path
    format: str = "html"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    media_types: set[str] = field(
        default_factory=lambda: {
            "photo",
            "video",
            "audio",
            "document",
            "voice",
            "sticker",
            "animation",
            "video_note",
        }
    )
    include_replies: bool = True
    include_forwards: bool = True
    max_file_size_mb: int = 500
    batch_size: int = 100


class ExportEngine:
    """Orchestrates the full export process."""

    def __init__(
        self,
        client: TeleExportClient,
        config: ExportConfig,
        progress_callback: Optional[Callable] = None,
    ):
        self.client = client
        self.config = config
        self.progress = ExportProgress(progress_callback)
        self.cancelled = False

    def cancel(self):
        """Cancel the current export."""
        self.cancelled = True

    async def run(self, export_id: str) -> dict:
        """Run the full export process."""
        self.progress.set_export_id(export_id)

        output_dir = self.config.output_dir / f"export_{datetime.now():%Y-%m-%d_%H-%M-%S}"
        output_dir.mkdir(parents=True, exist_ok=True)

        total_stats = {
            "export_id": export_id,
            "total_chats": 0,
            "total_messages": 0,
            "total_media": 0,
            "chats": [],
        }

        for chat_id in self.config.chat_ids:
            if self.cancelled:
                break

            try:
                chat_stats = await self._export_chat(chat_id, output_dir)
                total_stats["chats"].append(chat_stats)
                total_stats["total_messages"] += chat_stats["messages_count"]
                total_stats["total_media"] += chat_stats["media_count"]
                total_stats["total_chats"] += 1
            except Exception as e:
                self.progress.export_error(chat_id, str(e), recoverable=True)

        # Write metadata
        meta_path = output_dir / "export_metadata.json"
        meta_path.write_text(
            json.dumps(total_stats, indent=2, ensure_ascii=False, default=str)
        )

        return total_stats

    async def _export_chat(self, chat_id: int, output_dir: Path) -> dict:
        """Export a single chat."""
        entity = await self.client.client.get_entity(chat_id)
        chat_name = getattr(entity, "title", None) or (
            f"{getattr(entity, 'first_name', '') or ''} {getattr(entity, 'last_name', '') or ''}".strip()
        )

        # Create directories
        safe_name = "".join(c for c in chat_name if c.isalnum() or c in " _-")[:50]
        chat_dir = output_dir / safe_name
        chat_dir.mkdir(exist_ok=True)
        media_dir = chat_dir / "media"
        media_dir.mkdir(exist_ok=True)

        # Message fetcher
        fetcher = MessageFetcher(
            self.client.client,
            entity,
            date_from=self.config.date_from,
            date_to=self.config.date_to,
            batch_size=self.config.batch_size,
        )

        # Media downloader
        media_dl = MediaDownloader(
            self.client.client,
            media_dir,
            max_file_size=self.config.max_file_size_mb * 1024 * 1024,
            media_types=self.config.media_types,
        )

        messages = []
        media_count = 0

        async for batch in fetcher.iter_batches():
            if self.cancelled:
                break

            for msg in batch:
                if msg.media and self._should_download_media(msg.media):
                    media_path = await media_dl.download(msg)
                    if media_path:
                        media_count += 1

                messages.append(msg)

            # Update progress
            self.progress.update_chat(
                chat_id, chat_name, fetcher.processed, fetcher.total or fetcher.processed
            )

        # Format output
        formatter = self._get_formatter(chat_dir)
        formatter.format(chat_name, entity, messages, media_dir)

        # Emit chat complete
        self.progress.chat_complete(chat_id, len(messages), media_count)

        return {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "messages_count": len(messages),
            "media_count": media_count,
        }

    def _should_download_media(self, media) -> bool:
        """Check if media type should be downloaded."""
        if isinstance(media, MessageMediaPhoto):
            return "photo" in self.config.media_types
        if isinstance(media, MessageMediaDocument):
            doc = media.document
            if doc:
                mime = doc.mime_type or ""
                if "video" in mime and "video" in self.config.media_types:
                    return True
                if "audio" in mime and "audio" in self.config.media_types:
                    return True
                if "image" in mime and "photo" in self.config.media_types:
                    return True
                if "document" in self.config.media_types:
                    return True
        return False

    def _get_formatter(self, chat_dir: Path):
        """Get the appropriate formatter based on config."""
        formats = {
            "html": HTMLFormatter,
            "json": JSONFormatter,
            "csv": CSVFormatter,
        }
        formatter_class = formats.get(self.config.format, HTMLFormatter)
        return formatter_class(chat_dir)
