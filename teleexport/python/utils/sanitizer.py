"""HTML text sanitization utilities."""
import html
import re


def sanitize_html(text: str) -> str:
    """Sanitize text for safe HTML rendering.

    Escapes HTML entities while preserving newlines.
    """
    if not text:
        return ""

    # Escape HTML entities
    text = html.escape(text)

    # Preserve newlines as <br>
    text = text.replace("\n", "<br>")

    return text


def strip_html(text: str) -> str:
    """Remove all HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove characters that are not safe in filenames
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    # Limit length
    safe = safe[:200].strip()
    return safe or "unnamed"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[: max_length - len(suffix)] + suffix
