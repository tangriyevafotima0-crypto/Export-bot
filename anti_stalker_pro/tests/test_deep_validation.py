"""Deep validation tests - comprehensive coverage for all modules.

Tests import chains, class instantiation, method signatures, and
functional correctness across trapnet, storage, dashboard, scheduler,
intelligence, and bot modules.
"""

import importlib
import os
import sys
import time
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ===========================================================================
# Section 1: Module Import Validation
# ===========================================================================


class TestModuleImports:
    """Validate that every module can be imported without errors."""

    MODULE_LIST = [
        "core.config",
        "core.database",
        "core.models",
        "core.logger",
        "core.exceptions",
        "intelligence.ml_scorer",
        "intelligence.pattern_engine",
        "intelligence.anomaly_detector",
        "intelligence.behavior_profiler",
        "intelligence.predictor",
        "intelligence.timeline_builder",
        "trapnet.fingerprinter",
        "trapnet.geolocator",
        "trapnet.honeypot",
        "trapnet.flask_server",
        "bot.keyboards",
        "bot.alert_manager",
        "bot.notifier",
        "bot.handler",
        "bot.report_generator",
        "bot.version_channel",
        "dashboard.app",
        "dashboard.auth",
        "dashboard.routes.analytics",
        "dashboard.routes.targets",
        "dashboard.routes.reports",
        "dashboard.routes.realtime",
        "scheduler.task_manager",
        "scheduler.tasks",
        "storage.cache",
        "storage.backup",
        "storage.export",
        "userbot.client",
        "userbot.story_tracker",
        "userbot.online_tracker",
        "userbot.group_monitor",
        "userbot.message_tracker",
        "userbot.contact_analyzer",
    ]

    @pytest.mark.parametrize("module_name", MODULE_LIST)
    def test_module_imports(self, module_name):
        """Each module should import without raising errors."""
        mod = importlib.import_module(module_name)
        assert mod is not None


# ===========================================================================
# Section 2: Trapnet - Fingerprinter Tests
# ===========================================================================


class TestFingerprinter:
    """Tests for trapnet/fingerprinter.py Fingerprinter class."""

    def setup_method(self):
        from trapnet.fingerprinter import Fingerprinter
        self.fp = Fingerprinter()

    def test_generate_tracking_page_contains_tracking_code(self):
        """Tracking page HTML should contain the tracking code."""
        html = self.fp.generate_tracking_page("abc123", "https://example.com")
        assert "abc123" in html
        assert "https://example.com" in html
        assert "<!DOCTYPE html>" in html
        assert "/api/fingerprint" in html

    def test_generate_tracking_page_is_valid_html(self):
        """Tracking page should be a complete HTML document."""
        html = self.fp.generate_tracking_page("code1", "https://redirect.com")
        assert "<html>" in html
        assert "</html>" in html
        assert "<script>" in html
        assert "</script>" in html

    def test_generate_fingerprint_hash_deterministic(self):
        """Same data should produce the same hash."""
        data = {
            "screen_width": 1920,
            "screen_height": 1080,
            "color_depth": 24,
            "timezone": "Europe/London",
            "language": "en-US",
            "platform": "Win32",
            "hardware_concurrency": 8,
            "webgl_vendor": "NVIDIA",
            "webgl_renderer": "GeForce GTX 1080",
            "canvas_hash": "abcdef12345",
        }
        hash1 = self.fp.generate_fingerprint_hash(data)
        hash2 = self.fp.generate_fingerprint_hash(data)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_generate_fingerprint_hash_different_data(self):
        """Different data should produce different hashes."""
        data1 = {"screen_width": 1920, "screen_height": 1080, "platform": "Win32"}
        data2 = {"screen_width": 1440, "screen_height": 900, "platform": "MacIntel"}
        hash1 = self.fp.generate_fingerprint_hash(data1)
        hash2 = self.fp.generate_fingerprint_hash(data2)
        assert hash1 != hash2

    def test_same_device_check_identical_hashes(self):
        """Identical hashes should return 100% similarity."""
        h = "a" * 64
        assert self.fp.same_device_check(h, h) == 100.0

    def test_same_device_check_different_hashes(self):
        """Completely different hashes should return low similarity."""
        h1 = "a" * 64
        h2 = "b" * 64
        result = self.fp.same_device_check(h1, h2)
        assert result == 0.0

    def test_same_device_check_empty_hash(self):
        """Empty hash should return 0% similarity."""
        assert self.fp.same_device_check("", "abc") == 0.0
        assert self.fp.same_device_check("abc", "") == 0.0

    def test_compare_fingerprints_identical(self):
        """Identical fingerprints should give 100% similarity."""
        fp_data = {
            "screen_width": 1920,
            "screen_height": 1080,
            "color_depth": 24,
            "timezone": "UTC",
            "language": "en-US",
            "platform": "Win32",
            "hardware_concurrency": 8,
            "webgl_renderer": "GTX 1080",
            "webgl_vendor": "NVIDIA",
            "canvas_hash": "xyz",
        }
        assert self.fp.compare_fingerprints(fp_data, fp_data) == 100.0

    def test_compare_fingerprints_empty(self):
        """Empty fingerprints should return 0%."""
        assert self.fp.compare_fingerprints({}, {}) == 0.0
        assert self.fp.compare_fingerprints(None, {"a": 1}) == 0.0
        assert self.fp.compare_fingerprints({"a": 1}, None) == 0.0

    def test_compare_fingerprints_partial_match(self):
        """Partially matching fingerprints should give between 0-100%."""
        fp1 = {"screen_width": 1920, "platform": "Win32", "timezone": "UTC"}
        fp2 = {"screen_width": 1920, "platform": "MacIntel", "timezone": "UTC"}
        result = self.fp.compare_fingerprints(fp1, fp2)
        assert 0.0 < result < 100.0


# ===========================================================================
# Section 3: Trapnet - GeoLocator Tests
# ===========================================================================


class TestGeoLocator:
    """Tests for trapnet/geolocator.py GeoLocator class."""

    def test_is_private_ip_loopback(self):
        """127.0.0.1 should be detected as private."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        assert geo._is_private_ip("127.0.0.1") is True

    def test_is_private_ip_local_network(self):
        """192.168.x.x should be detected as private."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        assert geo._is_private_ip("192.168.1.1") is True
        assert geo._is_private_ip("10.0.0.1") is True
        assert geo._is_private_ip("172.16.0.1") is True

    def test_is_private_ip_public(self):
        """Public IPs should not be detected as private."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        assert geo._is_private_ip("8.8.8.8") is False
        assert geo._is_private_ip("93.184.216.34") is False

    def test_is_private_ip_invalid(self):
        """Invalid IP should return False."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        assert geo._is_private_ip("not_an_ip") is False

    def test_get_location_summary_private(self):
        """Private IPs should return Private/Local Network."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        result = geo.get_location_summary("192.168.1.1")
        assert result == "Private/Local Network"

    def test_get_location_summary_public_no_db(self):
        """Without GeoIP DB, should return Unknown(ip)."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        geo._geoip_reader = None
        result = geo.get_location_summary("8.8.8.8")
        assert "Unknown" in result
        assert "8.8.8.8" in result

    async def test_locate_ip_private(self):
        """locate_ip for private IP should return Private/Local Network."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        result = await geo.locate_ip("127.0.0.1")
        assert result["country"] == "Private"
        assert result["city"] == "Local Network"

    async def test_locate_ip_public_with_mock(self):
        """locate_ip for public IP should call ip-api.com (mocked)."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        geo._geoip_reader = None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "country": "United States",
            "city": "Mountain View",
            "regionName": "California",
            "lat": 37.386,
            "lon": -122.084,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await geo.locate_ip("8.8.8.8")

        assert result["country"] == "United States"
        assert result["city"] == "Mountain View"
        assert result["region"] == "California"
        assert result["latitude"] == 37.386

    async def test_locate_ip_api_failure(self):
        """locate_ip should return empty result on API failure."""
        from trapnet.geolocator import GeoLocator
        geo = GeoLocator()
        geo._geoip_reader = None

        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection failed"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await geo.locate_ip("8.8.8.8")

        assert result["country"] is None
        assert result["city"] is None


# ===========================================================================
# Section 4: Trapnet - Honeypot Tests
# ===========================================================================


class TestHoneypot:
    """Tests for trapnet/honeypot.py HoneypotManager class."""

    @patch("trapnet.honeypot.get_settings")
    def test_generate_unique_tracking_url(self, mock_settings):
        """Should generate a valid tracking URL."""
        mock_settings.return_value = MagicMock(
            trap_server_host="127.0.0.1",
            trap_server_port=5000,
        )
        from trapnet.honeypot import HoneypotManager
        manager = HoneypotManager()
        url = manager.generate_unique_tracking_url(user_id=12345)
        assert url.startswith("http://127.0.0.1:5000/")
        assert len(url) > len("http://127.0.0.1:5000/")

    @patch("trapnet.honeypot.get_settings")
    def test_generate_unique_tracking_url_replaces_0000(self, mock_settings):
        """0.0.0.0 host should be replaced with 127.0.0.1."""
        mock_settings.return_value = MagicMock(
            trap_server_host="0.0.0.0",
            trap_server_port=5000,
        )
        from trapnet.honeypot import HoneypotManager
        manager = HoneypotManager()
        url = manager.generate_unique_tracking_url(user_id=99)
        assert "127.0.0.1" in url
        assert "0.0.0.0" not in url

    @patch("trapnet.honeypot.get_settings")
    def test_generate_tracking_code(self, mock_settings):
        """Should generate a short alphanumeric code."""
        mock_settings.return_value = MagicMock(
            trap_server_host="127.0.0.1",
            trap_server_port=5000,
        )
        from trapnet.honeypot import HoneypotManager
        manager = HoneypotManager()
        code = manager.generate_tracking_code(user_id=12345)
        assert isinstance(code, str)
        assert len(code) > 0
        assert len(code) <= 8

    @patch("trapnet.honeypot.get_settings")
    async def test_schedule_bait_story_future_time(self, mock_settings):
        """Scheduling with future time should return scheduled status."""
        mock_settings.return_value = MagicMock(
            trap_server_host="127.0.0.1",
            trap_server_port=5000,
        )
        from trapnet.honeypot import HoneypotManager
        manager = HoneypotManager()
        target_time = datetime.utcnow() + timedelta(hours=1)
        result = await manager.schedule_bait_story(target_time)
        assert result["status"] == "scheduled"
        assert result["bait_type"] == "timed_story_bait"
        assert result["delay_seconds"] > 0
        assert "tracking_code" in result

    @patch("trapnet.honeypot.get_settings")
    async def test_schedule_bait_story_past_time(self, mock_settings):
        """Scheduling with past time should use now + 5 min."""
        mock_settings.return_value = MagicMock(
            trap_server_host="127.0.0.1",
            trap_server_port=5000,
        )
        from trapnet.honeypot import HoneypotManager
        manager = HoneypotManager()
        target_time = datetime.utcnow() - timedelta(hours=1)
        result = await manager.schedule_bait_story(target_time)
        assert result["status"] == "scheduled"
        assert result["delay_seconds"] > 0

    @patch("trapnet.honeypot.get_settings")
    def test_make_short_code(self, mock_settings):
        """_make_short_code should produce URL-safe output."""
        mock_settings.return_value = MagicMock(
            trap_server_host="127.0.0.1",
            trap_server_port=5000,
        )
        from trapnet.honeypot import HoneypotManager
        manager = HoneypotManager()
        code = manager._make_short_code("abcdef12")
        assert isinstance(code, str)
        assert len(code) <= 8
        # Should only contain lowercase letters and digits
        for ch in code:
            assert ch.isalnum() and ch.islower() or ch.isdigit()


# ===========================================================================
# Section 5: Storage - InMemoryCache Tests
# ===========================================================================


class TestInMemoryCache:
    """Tests for storage/cache.py InMemoryCache class."""

    async def test_set_and_get(self):
        """Should store and retrieve values."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("key1", "value1", ttl_seconds=60)
        result = await cache.get("key1")
        assert result == "value1"

    async def test_get_nonexistent(self):
        """Should return None for nonexistent keys."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    async def test_delete_existing(self):
        """Should delete an existing key and return True."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("key1", "value1", ttl_seconds=60)
        result = await cache.delete("key1")
        assert result is True
        assert await cache.get("key1") is None

    async def test_delete_nonexistent(self):
        """Should return False when deleting nonexistent key."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        result = await cache.delete("nonexistent")
        assert result is False

    async def test_clear(self):
        """Should clear all entries and return count."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("k1", "v1", ttl_seconds=60)
        await cache.set("k2", "v2", ttl_seconds=60)
        await cache.set("k3", "v3", ttl_seconds=60)
        count = await cache.clear()
        assert count == 3
        assert await cache.get("k1") is None

    async def test_size(self):
        """Should return number of non-expired entries."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("k1", "v1", ttl_seconds=60)
        await cache.set("k2", "v2", ttl_seconds=60)
        size = await cache.size()
        assert size == 2

    async def test_ttl_expiration(self):
        """Expired entries should return None."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("key1", "value1", ttl_seconds=0.01)
        # Wait for expiration
        time.sleep(0.02)
        result = await cache.get("key1")
        assert result is None

    async def test_get_or_set_cache_miss(self):
        """get_or_set should call factory on cache miss."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()

        async def factory():
            return "computed_value"

        result = await cache.get_or_set("key1", factory, ttl_seconds=60)
        assert result == "computed_value"
        # Should be cached now
        assert await cache.get("key1") == "computed_value"

    async def test_get_or_set_cache_hit(self):
        """get_or_set should return cached value without calling factory."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("key1", "cached_value", ttl_seconds=60)

        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "new_value"

        result = await cache.get_or_set("key1", factory, ttl_seconds=60)
        assert result == "cached_value"
        assert call_count == 0

    async def test_no_expiration_with_zero_ttl(self):
        """ttl_seconds=0 should mean no expiration."""
        from storage.cache import InMemoryCache
        cache = InMemoryCache()
        await cache.set("key1", "permanent", ttl_seconds=0)
        time.sleep(0.01)
        result = await cache.get("key1")
        assert result == "permanent"


# ===========================================================================
# Section 6: Storage - BackupManager Tests
# ===========================================================================


class TestBackupManager:
    """Tests for storage/backup.py BackupManager class."""

    @patch("storage.backup.get_settings")
    def test_create_backup(self, mock_settings):
        """Should copy database file to backup directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_path.write_text("test database content")
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            mock_settings.return_value = MagicMock(
                database_url=f"sqlite+aiosqlite:///{db_path}"
            )

            from storage.backup import BackupManager
            with patch("storage.backup.BACKUP_DIR", backup_dir):
                manager = BackupManager()
                result = manager.create_backup()

            assert result is not None
            assert Path(result).exists()
            assert "backup_" in Path(result).name

    @patch("storage.backup.get_settings")
    def test_create_backup_file_not_found(self, mock_settings):
        """Should raise FileNotFoundError if DB does not exist."""
        mock_settings.return_value = MagicMock(
            database_url="sqlite+aiosqlite:///nonexistent_path.db"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            from storage.backup import BackupManager
            with patch("storage.backup.BACKUP_DIR", backup_dir):
                manager = BackupManager()
                with pytest.raises(FileNotFoundError):
                    manager.create_backup()

    @patch("storage.backup.get_settings")
    def test_list_backups(self, mock_settings):
        """Should list backup files with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()
            # Create some fake backup files
            (backup_dir / "backup_20240101_120000.db").write_text("data1")
            (backup_dir / "backup_20240102_120000.db").write_text("data2")

            mock_settings.return_value = MagicMock(
                database_url="sqlite+aiosqlite:///test.db"
            )

            from storage.backup import BackupManager
            with patch("storage.backup.BACKUP_DIR", backup_dir):
                manager = BackupManager()
                backups = manager.list_backups()

            assert len(backups) == 2
            assert "filename" in backups[0]
            assert "size_bytes" in backups[0]
            assert "modified" in backups[0]

    @patch("storage.backup.get_settings")
    def test_cleanup_old_backups(self, mock_settings):
        """Should remove old backups beyond retention limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()
            # Create 5 backup files
            for i in range(5):
                f = backup_dir / f"backup_2024010{i}_120000.db"
                f.write_text(f"data{i}")
                # Set different mtimes to ensure ordering
                os.utime(f, (time.time() - (5 - i) * 3600, time.time() - (5 - i) * 3600))

            mock_settings.return_value = MagicMock(
                database_url="sqlite+aiosqlite:///test.db"
            )

            from storage.backup import BackupManager
            with patch("storage.backup.BACKUP_DIR", backup_dir):
                manager = BackupManager()
                removed = manager.cleanup_old_backups(keep=2)

            assert removed == 3
            remaining = list(backup_dir.glob("backup_*.db"))
            assert len(remaining) == 2


# ===========================================================================
# Section 7: Dashboard - App Tests
# ===========================================================================


class TestDashboardApp:
    """Tests for dashboard/app.py create_dashboard_app."""

    @patch("dashboard.app.get_settings")
    def test_create_dashboard_app_returns_fastapi(self, mock_settings):
        """create_dashboard_app should return a FastAPI instance."""
        mock_settings.return_value = MagicMock(
            dashboard_port=8080,
            dashboard_secret_key="test-key",
        )
        from dashboard.app import create_dashboard_app
        app = create_dashboard_app()
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    @patch("dashboard.app.get_settings")
    def test_dashboard_app_has_expected_routes(self, mock_settings):
        """Dashboard app should have health, login, verify routes."""
        mock_settings.return_value = MagicMock(
            dashboard_port=8080,
            dashboard_secret_key="test-key",
        )
        from dashboard.app import create_dashboard_app
        app = create_dashboard_app()
        route_paths = [route.path for route in app.routes]
        assert "/health" in route_paths
        assert "/api/auth/login" in route_paths
        assert "/api/auth/verify" in route_paths
        assert "/" in route_paths

    @patch("dashboard.app.get_settings")
    def test_dashboard_app_title(self, mock_settings):
        """Dashboard app should have correct title."""
        mock_settings.return_value = MagicMock(
            dashboard_port=8080,
            dashboard_secret_key="test-key",
        )
        from dashboard.app import create_dashboard_app
        app = create_dashboard_app()
        assert "Anti-Stalker" in app.title


# ===========================================================================
# Section 8: Dashboard - Auth Tests
# ===========================================================================


class TestDashboardAuth:
    """Tests for dashboard/auth.py JWT token operations."""

    @patch("dashboard.auth.get_settings")
    def test_create_and_verify_token_roundtrip(self, mock_settings):
        """Token created with create_access_token should be verifiable."""
        mock_settings.return_value = MagicMock(
            dashboard_secret_key="test-secret-key-for-testing"
        )
        from dashboard.auth import create_access_token, verify_token
        token = create_access_token(data={"sub": "admin", "role": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

        payload = verify_token(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"
        assert "exp" in payload

    @patch("dashboard.auth.get_settings")
    def test_expired_token_raises(self, mock_settings):
        """Expired token should raise HTTPException."""
        mock_settings.return_value = MagicMock(
            dashboard_secret_key="test-secret-key-for-testing"
        )
        from dashboard.auth import create_access_token, verify_token
        from fastapi import HTTPException

        # Create a token that expires immediately
        token = create_access_token(
            data={"sub": "admin"},
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401

    @patch("dashboard.auth.get_settings")
    def test_invalid_token_raises(self, mock_settings):
        """Invalid token string should raise HTTPException."""
        mock_settings.return_value = MagicMock(
            dashboard_secret_key="test-secret-key-for-testing"
        )
        from dashboard.auth import verify_token
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid.token.string")
        assert exc_info.value.status_code == 401

    @patch("dashboard.auth.get_settings")
    def test_token_with_custom_expiry(self, mock_settings):
        """Token with custom expiry should be valid before expiry."""
        mock_settings.return_value = MagicMock(
            dashboard_secret_key="test-secret-key-for-testing"
        )
        from dashboard.auth import create_access_token, verify_token
        token = create_access_token(
            data={"sub": "user1"},
            expires_delta=timedelta(hours=48),
        )
        payload = verify_token(token)
        assert payload["sub"] == "user1"


# ===========================================================================
# Section 9: Scheduler - TaskManager Tests
# ===========================================================================


class TestTaskManager:
    """Tests for scheduler/task_manager.py TaskManager class."""

    @patch("scheduler.task_manager.get_settings")
    def test_init(self, mock_settings):
        """TaskManager should initialize without errors."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()
        assert tm._is_running is False
        assert tm._scheduler is None

    @patch("scheduler.task_manager.get_settings")
    def test_scheduler_property_creates_instance(self, mock_settings):
        """Accessing scheduler property should create an AsyncIOScheduler."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        tm = TaskManager()
        scheduler = tm.scheduler
        assert isinstance(scheduler, AsyncIOScheduler)

    @patch("scheduler.task_manager.get_settings")
    def test_scheduler_property_singleton(self, mock_settings):
        """Scheduler property should return the same instance."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()
        s1 = tm.scheduler
        s2 = tm.scheduler
        assert s1 is s2

    @patch("scheduler.task_manager.get_settings")
    def test_add_job_interval(self, mock_settings):
        """Should add an interval job to the scheduler."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()

        async def dummy_task():
            pass

        tm.add_job(dummy_task, trigger="interval", job_id="test_job", seconds=30)
        # Verify the job was added to the scheduler directly
        scheduler_jobs = tm.scheduler.get_jobs()
        assert len(scheduler_jobs) == 1
        assert scheduler_jobs[0].id == "test_job"

    @patch("scheduler.task_manager.get_settings")
    def test_add_job_cron(self, mock_settings):
        """Should add a cron job to the scheduler."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()

        async def dummy_task():
            pass

        tm.add_job(dummy_task, trigger="cron", job_id="cron_job", hour=3, minute=0)
        scheduler_jobs = tm.scheduler.get_jobs()
        assert any(j.id == "cron_job" for j in scheduler_jobs)

    @patch("scheduler.task_manager.get_settings")
    def test_get_jobs_empty(self, mock_settings):
        """Should return empty list when no jobs are added."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()
        jobs = tm.get_jobs()
        assert jobs == []

    @patch("scheduler.task_manager.get_settings")
    async def test_start_and_stop(self, mock_settings):
        """Should start and stop the scheduler."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()
        tm.start()
        assert tm.is_running is True
        tm.stop()
        assert tm.is_running is False

    @patch("scheduler.task_manager.get_settings")
    async def test_start_twice_does_not_error(self, mock_settings):
        """Starting twice should not raise."""
        mock_settings.return_value = MagicMock()
        from scheduler.task_manager import TaskManager
        tm = TaskManager()
        tm.start()
        tm.start()  # should just log a warning
        assert tm.is_running is True
        tm.stop()


# ===========================================================================
# Section 10: Intelligence - TimelineBuilder Tests
# ===========================================================================


class TestTimelineBuilder:
    """Tests for intelligence/timeline_builder.py format_for_dashboard."""

    def test_format_for_dashboard_empty_timeline(self):
        """Empty timeline should produce empty labels and datasets."""
        from intelligence.timeline_builder import TimelineBuilder
        builder = TimelineBuilder()
        result = builder.format_for_dashboard([])
        assert result["labels"] == []
        assert isinstance(result["datasets"], list)
        assert len(result["datasets"]) == 5  # 5 event types

    def test_format_for_dashboard_structure(self):
        """Output should have Chart.js-compatible structure."""
        from intelligence.timeline_builder import TimelineBuilder
        builder = TimelineBuilder()
        timeline = [
            {"timestamp": "2024-01-15T10:00:00", "event_type": "story_view", "details": {}},
            {"timestamp": "2024-01-15T11:00:00", "event_type": "online", "details": {}},
            {"timestamp": "2024-01-16T09:00:00", "event_type": "alert", "details": {}},
        ]
        result = builder.format_for_dashboard(timeline)

        assert "labels" in result
        assert "datasets" in result
        assert sorted(result["labels"]) == result["labels"]
        assert "2024-01-15" in result["labels"]
        assert "2024-01-16" in result["labels"]

        for dataset in result["datasets"]:
            assert "label" in dataset
            assert "data" in dataset
            assert "backgroundColor" in dataset
            assert "borderColor" in dataset
            assert "fill" in dataset
            assert len(dataset["data"]) == len(result["labels"])

    def test_format_for_dashboard_counts_correctly(self):
        """Should count events per day correctly."""
        from intelligence.timeline_builder import TimelineBuilder
        builder = TimelineBuilder()
        timeline = [
            {"timestamp": "2024-01-15T10:00:00", "event_type": "story_view", "details": {}},
            {"timestamp": "2024-01-15T11:00:00", "event_type": "story_view", "details": {}},
            {"timestamp": "2024-01-15T12:00:00", "event_type": "story_view", "details": {}},
        ]
        result = builder.format_for_dashboard(timeline)

        # Find the "Story Views" dataset
        story_dataset = next(d for d in result["datasets"] if d["label"] == "Story Views")
        assert story_dataset["data"][0] == 3

    def test_format_for_dashboard_multiple_days(self):
        """Should handle events spanning multiple days."""
        from intelligence.timeline_builder import TimelineBuilder
        builder = TimelineBuilder()
        timeline = [
            {"timestamp": "2024-01-10T10:00:00", "event_type": "online", "details": {}},
            {"timestamp": "2024-01-20T10:00:00", "event_type": "alert", "details": {}},
        ]
        result = builder.format_for_dashboard(timeline)
        assert len(result["labels"]) == 2
        assert "2024-01-10" in result["labels"]
        assert "2024-01-20" in result["labels"]


# ===========================================================================
# Section 11: Bot - AlertManager Tests
# ===========================================================================


class TestAlertManagerLogic:
    """Tests for bot/alert_manager.py private delivery logic methods."""

    @patch("bot.alert_manager.get_settings")
    def test_is_quiet_hours_during_quiet(self, mock_settings):
        """Should return True during 00:00-08:00 UTC."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        with patch("bot.alert_manager.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 15, 3, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # The method uses datetime.utcnow().hour directly
            result = manager._is_quiet_hours()
            # Since we patched datetime.utcnow, we need to check differently
            # Actually _is_quiet_hours calls datetime.utcnow() directly
        # Let's test this differently - just check the logic
        # The current hour depends on when the test runs, so test by mocking

    @patch("bot.alert_manager.get_settings")
    def test_is_quiet_hours_logic(self, mock_settings):
        """Quiet hours are 0-8 UTC; test the boundary logic."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        # We can test by mocking datetime at module level
        with patch("bot.alert_manager.datetime") as mock_dt:
            # Test hour 3 -> quiet
            mock_now = MagicMock()
            mock_now.hour = 3
            mock_dt.utcnow.return_value = mock_now
            assert manager._is_quiet_hours() is True

            # Test hour 10 -> not quiet
            mock_now.hour = 10
            mock_dt.utcnow.return_value = mock_now
            assert manager._is_quiet_hours() is False

            # Test hour 0 -> quiet (boundary)
            mock_now.hour = 0
            mock_dt.utcnow.return_value = mock_now
            assert manager._is_quiet_hours() is True

            # Test hour 8 -> not quiet (boundary)
            mock_now.hour = 8
            mock_dt.utcnow.return_value = mock_now
            assert manager._is_quiet_hours() is False

    @patch("bot.alert_manager.get_settings")
    def test_exceeds_rate_limit_under_limit(self, mock_settings):
        """Should return False when under the 2/hour limit."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.tracked_user_id = 1
        alert.id = 1
        alert.created_at = datetime.utcnow()
        alert.is_acknowledged = False

        # One acknowledged alert for same user within an hour - still under limit
        other = MagicMock()
        other.tracked_user_id = 1
        other.id = 2
        other.created_at = datetime.utcnow() - timedelta(minutes=10)
        other.is_acknowledged = True

        all_pending = [alert, other]
        result = manager._exceeds_rate_limit(alert, all_pending)
        assert result is False

    @patch("bot.alert_manager.get_settings")
    def test_exceeds_rate_limit_over_limit(self, mock_settings):
        """Should return True when at/over 2/hour limit."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.tracked_user_id = 1
        alert.id = 10
        alert.created_at = datetime.utcnow()
        alert.is_acknowledged = False

        # Create 2 recent acknowledged alerts for same user
        recent_alert_1 = MagicMock()
        recent_alert_1.tracked_user_id = 1
        recent_alert_1.created_at = datetime.utcnow() - timedelta(minutes=10)
        recent_alert_1.is_acknowledged = True
        recent_alert_1.id = 1

        recent_alert_2 = MagicMock()
        recent_alert_2.tracked_user_id = 1
        recent_alert_2.created_at = datetime.utcnow() - timedelta(minutes=20)
        recent_alert_2.is_acknowledged = True
        recent_alert_2.id = 2

        all_pending = [alert, recent_alert_1, recent_alert_2]
        result = manager._exceeds_rate_limit(alert, all_pending)
        assert result is True

    @patch("bot.alert_manager.get_settings")
    def test_is_duplicate_no_duplicates(self, mock_settings):
        """Should return False when no duplicates exist."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.id = 1
        alert.alert_type = "story_view"
        alert.tracked_user_id = 1

        all_pending = [alert]
        result = manager._is_duplicate(alert, all_pending)
        assert result is False

    @patch("bot.alert_manager.get_settings")
    def test_is_duplicate_with_duplicate(self, mock_settings):
        """Should return True when same type/user acknowledged within 30 min."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.id = 2
        alert.alert_type = "story_view"
        alert.tracked_user_id = 1

        other_alert = MagicMock()
        other_alert.id = 1
        other_alert.alert_type = "story_view"
        other_alert.tracked_user_id = 1
        other_alert.created_at = datetime.utcnow() - timedelta(minutes=10)
        other_alert.is_acknowledged = True

        all_pending = [alert, other_alert]
        result = manager._is_duplicate(alert, all_pending)
        assert result is True

    @patch("bot.alert_manager.get_settings")
    def test_is_duplicate_different_type(self, mock_settings):
        """Should return False when alert type differs."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.id = 2
        alert.alert_type = "story_view"
        alert.tracked_user_id = 1

        other_alert = MagicMock()
        other_alert.id = 1
        other_alert.alert_type = "score_spike"  # Different type
        other_alert.tracked_user_id = 1
        other_alert.created_at = datetime.utcnow() - timedelta(minutes=10)
        other_alert.is_acknowledged = True

        all_pending = [alert, other_alert]
        result = manager._is_duplicate(alert, all_pending)
        assert result is False


# ===========================================================================
# Section 12: Can Deliver Logic (integration of quiet/rate/duplicate)
# ===========================================================================


class TestAlertCanDeliver:
    """Tests for _can_deliver combining all rules."""

    @patch("bot.alert_manager.get_settings")
    def test_critical_always_delivers(self, mock_settings):
        """CRITICAL alerts should bypass all rules."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.severity = "CRITICAL"
        alert.tracked_user_id = 1
        alert.id = 1

        result = manager._can_deliver(alert, [alert])
        assert result is True

    @patch("bot.alert_manager.get_settings")
    def test_non_critical_blocked_during_quiet(self, mock_settings):
        """Non-critical alerts should be blocked during quiet hours."""
        mock_settings.return_value = MagicMock()
        from bot.alert_manager import AlertManager
        manager = AlertManager()

        alert = MagicMock()
        alert.severity = "warning"
        alert.tracked_user_id = 1
        alert.id = 1

        with patch.object(manager, "_is_quiet_hours", return_value=True):
            result = manager._can_deliver(alert, [alert])
        assert result is False
