"""File utility functions for safe operations."""
import os
import re
from pathlib import Path


def safe_filename(name: str, max_length: int = 100) -> str:
    """Generate a safe filename from arbitrary text.

    Removes/replaces characters not safe for filesystems.
    """
    # Replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Replace multiple spaces/underscores
    safe = re.sub(r"[_\s]+", "_", safe)
    # Strip leading/trailing dots and spaces
    safe = safe.strip(". ")
    # Limit length
    safe = safe[:max_length]
    return safe or "unnamed"


def ensure_dir(path: Path) -> Path:
    """Create directory and parents if they don't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_unique_path(path: Path) -> Path:
    """Get a unique path by appending a number suffix if file exists."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


def count_files_in_dir(directory: Path, pattern: str = "*") -> int:
    """Count files matching pattern in a directory."""
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.glob(pattern))
