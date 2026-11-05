# Changelog

All notable changes to the Anti-Stalker Intelligence System are documented here.

## [2.1.0] - 2026-11-05

### Fixed
- **Service Orchestration (`main.py`)**: Wired `create_dashboard_app()`, `create_flask_app()`, `setup_bot_handlers()`, and `TaskManager.init_scheduler()` to prevent services from running as empty stubs.
- **Asyncio Coroutine Reuse (`userbot/client.py`)**: Fixed `safe_request()` to prevent `RuntimeError: cannot reuse already awaited coroutine` on `FloodWaitError` retries.
- **Datetime Offset Type Conflict (`userbot/online_tracker.py`)**: Normalized timezone-aware and naive timestamps before calculating session durations in `_handle_offline()`.
- **Story Tracker Request Logic (`userbot/story_tracker.py`)**: Fixed `check_all_stories()` to query user's own active stories (`GetPeerStoriesRequest(peer='me')`) rather than other peers' stories.
- **Group Reactions Attribution (`userbot/group_monitor.py`)**: Added `GetMessageReactionsListRequest` to resolve reactor IDs for owner messages in mutual groups.
- **Database Model Integer Overflow (`core/models.py`)**: Changed `telegram_id` to `BigInteger` for 64-bit Telegram user ID safety.
- **Circular Time-of-Day Math (`intelligence/ml_scorer.py`)**: Replaced linear hour variance with directional/circular statistics for viewing time variance calculation.
- **Safe Hot Backups (`storage/backup.py`)**: Introduced `sqlite3.backup()` hot backup for active WAL mode databases with fallback.
- **Starlette Route Introspection (`tests/test_deep_validation.py`)**: Fixed nested `_IncludedRouter` route path inspection.

### Added
- `TrackingLink` model and tracking code resolution mapping between honeypot URLs and tracked targets (`trapnet/honeypot.py` & `trapnet/flask_server.py`).
- Telegram WebApp button integration for `/dashboard` and main menu keyboard (`bot/handler.py` & `bot/keyboards.py`).
- Root `.gitignore` for Python, SQLite, session, and cache files.

## [2.0.0] - 2025-06-09

### Added
- Version update channel feature for automated Telegram announcements
- `/version` bot command to display current application version and system info
- `VersionChannel` class for posting version updates, changelog entries, and system status
- `version_channel_id` configuration field for specifying the announcement channel
- `app_version` configuration field for tracking current application version
- Startup version announcement posted automatically on boot
- CHANGELOG.md for tracking version history

### Fixed
- Method call mismatches in scheduler tasks (check_all_targets, run, deep_analysis)
- Missing `rebuild_all_profiles` method in BehaviorProfiler
- Incorrect method names in dashboard routes and storage export modules
- All 35 existing tests passing with full coverage

### Changed
- System version bumped to 2.0.0
- Improved error handling across bot notification modules
