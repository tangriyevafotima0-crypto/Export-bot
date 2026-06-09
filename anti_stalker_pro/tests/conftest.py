"""Shared test fixtures and configuration for pytest."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment variables for testing before any imports that use Settings
os.environ.setdefault("TELEGRAM_API_ID", "12345")
os.environ.setdefault("TELEGRAM_API_HASH", "test_hash_value_abc123")
os.environ.setdefault("TELEGRAM_PHONE", "+1234567890")
os.environ.setdefault("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
os.environ.setdefault("MY_TELEGRAM_ID", "987654321")
os.environ.setdefault("DASHBOARD_SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test_anti_stalker.db")
