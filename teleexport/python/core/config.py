"""TeleExport configuration constants and directory setup."""
import os
from pathlib import Path

# Base directories
HOME_DIR = Path.home()
TELEEXPORT_DIR = HOME_DIR / ".teleexport"
SESSION_DIR = TELEEXPORT_DIR / "sessions"
CONFIG_DIR = TELEEXPORT_DIR / "config"
EXPORTS_DIR = HOME_DIR / "TeleExport" / "exports"

# Default settings
DEFAULT_SETTINGS = {
    "output_dir": str(EXPORTS_DIR),
    "format": "html",
    "media_types": ["photo", "video", "audio", "document", "voice", "sticker"],
    "max_file_size_mb": 500,
    "batch_size": 100,
    "include_replies": True,
    "include_forwards": True,
}


def setup_dirs():
    """Create all required directories if they don't exist."""
    for directory in [SESSION_DIR, CONFIG_DIR, EXPORTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
