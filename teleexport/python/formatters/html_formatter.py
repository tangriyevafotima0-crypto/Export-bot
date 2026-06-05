"""HTML formatter using Jinja2 templates for beautiful chat export."""
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape


class HTMLFormatter:
    """Formats chat messages as beautiful HTML with dark theme."""

    def __init__(self, output_dir: Path = None, templates_dir: Path = None):
        self.output_dir = output_dir
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        # Custom filters
        self.env.filters["format_date"] = self._format_date
        self.env.filters["format_time"] = self._format_time
        self.env.filters["message_type"] = self._get_message_type

    def format(
        self,
        chat_name: str,
        entity,
        messages: list,
        media_dir: Path,
    ) -> Path:
        """Format a chat to HTML file."""
        # Group messages by date
        grouped = self._group_by_date(messages)

        # Collect participants
        participants = self._collect_participants(messages)

        template = self.env.get_template("chat.html")
        html = template.render(
            chat_name=chat_name,
            chat_type=self._get_chat_type(entity),
            grouped_messages=grouped,
            participants=participants,
            media_relative_path="media/",
            export_date=datetime.now(),
            total_messages=len(messages),
        )

        output_path = self.output_dir / f"{chat_name}.html"
        output_path.write_text(html, encoding="utf-8")

        return output_path

    def _group_by_date(self, messages: list) -> dict:
        """Group messages by date."""
        groups = {}
        for msg in sorted(messages, key=lambda m: m.date):
            date_key = msg.date.strftime("%Y-%m-%d")
            if date_key not in groups:
                groups[date_key] = []
            groups[date_key].append(msg)
        return groups

    def _collect_participants(self, messages: list) -> dict:
        """Collect all unique participants from messages."""
        participants = {}
        seen = set()
        for msg in messages:
            sender = getattr(msg, "sender_id", None)
            if sender and sender not in seen:
                seen.add(sender)
                participants[sender] = {
                    "id": sender,
                    "name": getattr(msg, "sender_name", "Unknown"),
                }
        return participants

    @staticmethod
    def _format_date(dt: datetime) -> str:
        """Format date for display."""
        return dt.strftime("%B %d, %Y")

    @staticmethod
    def _format_time(dt: datetime) -> str:
        """Format time for display."""
        return dt.strftime("%H:%M")

    @staticmethod
    def _get_message_type(msg) -> str:
        """Determine message type."""
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
        if getattr(msg, "contact", None):
            return "contact"
        if getattr(msg, "poll", None):
            return "poll"
        if getattr(msg, "geo", None):
            return "location"
        return "text"

    @staticmethod
    def _get_chat_type(entity) -> str:
        """Determine chat type from entity."""
        if hasattr(entity, "broadcast") and entity.broadcast:
            return "channel"
        if hasattr(entity, "megagroup") and entity.megagroup:
            return "group"
        return "private"
