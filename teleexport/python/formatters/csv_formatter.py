"""CSV formatter for tabular chat export."""
import csv
from pathlib import Path
from datetime import datetime


class CSVFormatter:
    """Formats chat messages as CSV file."""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir

    def format(
        self,
        chat_name: str,
        entity,
        messages: list,
        media_dir: Path,
    ) -> Path:
        """Format messages as CSV file."""
        output_path = self.output_dir / f"{chat_name}.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "id",
                "date",
                "time",
                "sender_id",
                "sender_name",
                "text",
                "media_type",
                "reply_to",
                "forwarded",
            ])

            # Messages
            for msg in sorted(messages, key=lambda m: m.date):
                writer.writerow([
                    msg.id,
                    msg.date.strftime("%Y-%m-%d") if msg.date else "",
                    msg.date.strftime("%H:%M:%S") if msg.date else "",
                    getattr(msg, "sender_id", ""),
                    getattr(msg, "sender_name", ""),
                    (msg.text or "").replace("\n", " "),
                    self._get_media_type(msg),
                    getattr(msg, "reply_to_msg_id", ""),
                    "yes" if getattr(msg, "fwd_from", None) else "no",
                ])

        return output_path

    @staticmethod
    def _get_media_type(msg) -> str:
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
        return ""
