# Changelog

All notable changes to the Anti-Stalker Intelligence System are documented here.

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
