"""Session file management for TeleExport."""
import os
from pathlib import Path
from datetime import datetime

from .config import SESSION_DIR


class SessionManager:
    """Manages Telethon session files."""

    def __init__(self, session_dir: Path = None):
        self.session_dir = session_dir or SESSION_DIR

    def list_sessions(self) -> list[dict]:
        """List all available sessions."""
        sessions = []
        if not self.session_dir.exists():
            return sessions

        for f in self.session_dir.glob("*.session"):
            stat = f.stat()
            sessions.append({
                "name": f.stem,
                "path": str(f),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return sessions

    def delete_session(self, name: str) -> bool:
        """Delete a session file by name."""
        session_path = self.session_dir / f"{name}.session"
        if session_path.exists():
            session_path.unlink()
            return True
        return False

    def get_session_info(self, name: str) -> dict | None:
        """Get info about a specific session."""
        session_path = self.session_dir / f"{name}.session"
        if not session_path.exists():
            return None

        stat = session_path.stat()
        return {
            "name": name,
            "path": str(session_path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }

    def session_exists(self, name: str) -> bool:
        """Check if a session file exists."""
        return (self.session_dir / f"{name}.session").exists()
