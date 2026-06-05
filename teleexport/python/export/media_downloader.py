"""Media file downloader with deduplication and size limits."""
from pathlib import Path
from typing import Optional


class MediaDownloader:
    """Downloads media files with dedup via file_id cache."""

    def __init__(
        self,
        client,
        output_dir: Path,
        max_file_size: int = 500 * 1024 * 1024,
        media_types: set[str] = None,
    ):
        self.client = client
        self.output_dir = output_dir
        self.max_file_size = max_file_size
        self.media_types = media_types or set()
        self._downloaded: dict[str, Path] = {}  # file_id -> path (dedup cache)

    async def download(self, message) -> Optional[Path]:
        """Download a media file with deduplication."""
        try:
            # Check file size
            file_size = 0
            if message.media:
                file_size = getattr(message.media, "size", 0) or 0
                if hasattr(message.media, "document") and message.media.document:
                    file_size = message.media.document.size or 0

            if file_size and file_size > self.max_file_size:
                return None

            # Dedup check
            file_id = self._get_file_id(message)
            if file_id and file_id in self._downloaded:
                return self._downloaded[file_id]

            # Generate filename
            filename = self._generate_filename(message)
            filepath = self.output_dir / filename

            # Skip if already exists
            if filepath.exists():
                if file_id:
                    self._downloaded[file_id] = filepath
                return filepath

            # Download
            downloaded = await message.download_media(file=str(filepath))

            if downloaded:
                if file_id:
                    self._downloaded[file_id] = filepath
                return filepath

        except Exception:
            pass

        return None

    def _get_file_id(self, message) -> Optional[str]:
        """Get a unique file ID for deduplication."""
        if message.photo:
            return f"photo_{message.photo.id}"
        if message.document:
            return f"doc_{message.document.id}"
        return None

    def _generate_filename(self, message) -> str:
        """Generate a filename with date prefix and original name or hash."""
        date_str = message.date.strftime("%Y-%m-%d_%H-%M-%S")
        msg_id = message.id

        # Use original filename if available
        if message.file and message.file.name:
            orig = message.file.name.replace("/", "_")[:100]
            return f"{date_str}_{msg_id}_{orig}"

        # Determine extension from media type
        if message.photo:
            ext = "jpg"
        elif message.video:
            ext = "mp4"
        elif message.audio:
            ext = "mp3"
        elif message.voice:
            ext = "ogg"
        else:
            ext = "bin"

        return f"{date_str}_{msg_id}_media.{ext}"
