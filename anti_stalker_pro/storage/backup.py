"""Database backup and restore management.

Handles automated SQLite database backups with timestamp naming,
restore functionality, and cleanup of old backup files.
"""

import shutil
from datetime import datetime
from pathlib import Path

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
BACKUP_DIR = DATA_DIR / "backups"


class BackupManager:
    """Manages SQLite database backup, restore, and cleanup operations.

    Backups are stored in data/backups/ with timestamp-based filenames.
    Old backups are automatically cleaned up beyond the retention limit.
    """

    def __init__(self) -> None:
        """Initialize the BackupManager and ensure backup directory exists."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._settings = get_settings()

    def _get_db_path(self) -> Path:
        """Extract the SQLite file path from the database URL.

        Returns:
            Path: Resolved path to the SQLite database file.
        """
        db_url = self._settings.database_url
        if ":///" in db_url:
            path_part = db_url.split(":///", 1)[1]
        elif "://" in db_url:
            path_part = db_url.split("://", 1)[1]
        else:
            path_part = db_url

        db_path = Path(path_part)
        if not db_path.is_absolute():
            db_path = Path(__file__).parent.parent / db_path
        return db_path

    def create_backup(self) -> str:
        """Create a backup of the SQLite database.

        Copies the database file to the backups directory with a
        timestamp in the filename.

        Returns:
            str: Path to the created backup file.

        Raises:
            FileNotFoundError: If the database file does not exist.
        """
        db_path = self._get_db_path()

        if not db_path.exists():
            logger.warning(f"Database file not found: {db_path}")
            raise FileNotFoundError(f"Database file not found: {db_path}")

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = BACKUP_DIR / backup_filename

        shutil.copy2(str(db_path), str(backup_path))
        logger.info(f"Database backup created: {backup_path}")
        return str(backup_path)

    def restore_backup(self, backup_path: str) -> bool:
        """Restore the database from a backup file.

        Replaces the current database with the specified backup.

        Args:
            backup_path: Path to the backup file to restore from.

        Returns:
            bool: True if restore was successful, False otherwise.
        """
        source = Path(backup_path)
        if not source.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        db_path = self._get_db_path()

        try:
            if db_path.exists():
                pre_restore = BACKUP_DIR / f"pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(str(db_path), str(pre_restore))
                logger.info(f"Pre-restore backup saved: {pre_restore}")

            shutil.copy2(str(source), str(db_path))
            logger.info(f"Database restored from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def cleanup_old_backups(self, keep: int = 7) -> int:
        """Remove old backups beyond the retention limit.

        Keeps the most recent 'keep' backups and removes the rest.

        Args:
            keep: Number of most recent backups to retain (default 7).

        Returns:
            int: Number of backup files removed.
        """
        backups = sorted(
            BACKUP_DIR.glob("backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if len(backups) <= keep:
            return 0

        to_remove = backups[keep:]
        removed = 0
        for backup in to_remove:
            try:
                backup.unlink()
                removed += 1
            except Exception as e:
                logger.error(f"Failed to remove backup {backup}: {e}")

        logger.info(f"Cleaned up {removed} old backups (keeping {keep})")
        return removed

    def list_backups(self) -> list[dict]:
        """List all available backup files.

        Returns:
            list[dict]: List of backup info with path, filename, size, and date.
        """
        backups = sorted(
            BACKUP_DIR.glob("backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [
            {
                "path": str(b),
                "filename": b.name,
                "size_bytes": b.stat().st_size,
                "modified": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
            }
            for b in backups
        ]

    def auto_backup(self) -> str:
        """Perform an automated backup with cleanup.

        Creates a new backup and removes old ones beyond the retention limit.
        Called by the scheduler on a daily basis.

        Returns:
            str: Path to the created backup file.
        """
        backup_path = self.create_backup()
        self.cleanup_old_backups(keep=7)
        return backup_path
