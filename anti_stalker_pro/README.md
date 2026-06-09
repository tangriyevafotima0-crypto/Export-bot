# Anti-Stalker Intelligence System

Advanced Telegram monitoring platform that detects and profiles potential stalkers using behavioral analysis, ML-based scoring, and real-time alerting.

## Features

- **Userbot Monitoring** - Story view tracking, online status monitoring, bio link fingerprinting
- **ML Scoring Engine** - 8-feature weighted scoring with NORMAL/CURIOUS/SUSPICIOUS/STALKER classification
- **Pattern Detection** - Identifies NIGHT_STALKER, IMMEDIATE_RESPONDER, DAILY_CHECKER, SILENT_OBSERVER behaviors
- **Behavior Profiling** - Builds comprehensive activity profiles for tracked users
- **Real-time Dashboard** - FastAPI web interface with WebSocket live updates and Chart.js visualizations
- **Trap Network** - Flask-based honeypot links with device fingerprinting and geolocation
- **Automated Reports** - Daily PDF reports with suspicion breakdowns
- **Smart Alerts** - Threshold-based notifications via Telegram bot
- **Data Export** - CSV, JSON, and PDF export formats
- **Automated Backups** - Daily SQLite backups with retention policy

## Architecture

```
anti_stalker_pro/
|-- core/           # Config, database, models, logger, exceptions
|-- userbot/        # Telethon userbot (story tracker, online tracker)
|-- intelligence/   # ML scorer, pattern engine, behavior profiler, predictor
|-- trapnet/        # Flask trap server, fingerprinter, honeypot, geolocator
|-- bot/            # Telegram bot (handler, notifier, report generator, alerts)
|-- dashboard/      # FastAPI web dashboard with real-time WebSocket
|-- scheduler/      # APScheduler task management
|-- storage/        # Cache, data export, backup manager
|-- tests/          # pytest test suite
|-- data/           # Database, logs, backups, exports
|-- main.py         # Application entry point
```

## Installation

### Prerequisites

- Python 3.11+
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)
- Telegram Bot token from [@BotFather](https://t.me/BotFather)

### Manual Setup

```bash
cd anti_stalker_pro

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the application
python main.py
```

### Docker Setup

```bash
cd anti_stalker_pro

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

## Configuration

All configuration is managed through environment variables (`.env` file):

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_API_ID` | Telegram API ID from my.telegram.org | Required |
| `TELEGRAM_API_HASH` | Telegram API hash | Required |
| `TELEGRAM_PHONE` | Phone number for userbot | Required |
| `BOT_TOKEN` | Telegram Bot API token | Required |
| `MY_TELEGRAM_ID` | Your Telegram numeric user ID | Required |
| `DASHBOARD_SECRET_KEY` | Secret key for JWT auth | change-me |
| `DASHBOARD_PORT` | Dashboard server port | 8443 |
| `TRAP_SERVER_PORT` | Trap server port | 5000 |
| `DATABASE_URL` | SQLAlchemy async database URL | sqlite+aiosqlite:///data/anti_stalker.db |
| `ONLINE_CHECK_INTERVAL` | Online check interval (seconds) | 30 |
| `STORY_CHECK_INTERVAL` | Story check interval (seconds) | 60 |
| `ANALYSIS_INTERVAL` | Pattern analysis interval (seconds) | 3600 |
| `ALERT_THRESHOLD` | Score threshold for alerts (0-100) | 70 |
| `MAX_TRACKED_USERS` | Maximum tracked users | 50 |
| `LOG_LEVEL` | Application log level | INFO |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot and show welcome message |
| `/status` | Current monitoring status and stats |
| `/targets` | List all tracked users with scores |
| `/add <user_id>` | Add a new target for monitoring |
| `/remove <user_id>` | Remove a target from monitoring |
| `/score <user_id>` | Get detailed score breakdown |
| `/report` | Generate daily summary report |
| `/alerts` | View recent alerts |
| `/export <user_id>` | Export data for a user |
| `/settings` | View/modify settings |

## Dashboard

The web dashboard provides real-time monitoring at `http://localhost:8443`:

- **Overview** - Stats cards, top suspects, real-time event feed
- **Targets** - CRUD management of tracked users
- **Analytics** - Heatmaps, score history charts, daily distributions
- **Alerts** - Alert history with severity levels
- **Bio Tracker** - Device distribution and visit tracking

### Authentication

The dashboard uses JWT authentication. Login with `DASHBOARD_SECRET_KEY` as the password.

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Authenticate and get JWT token |
| GET | `/api/auth/verify` | Verify token validity |
| GET | `/api/analytics/overview` | Dashboard overview stats |
| GET | `/api/analytics/heatmap/{user_id}` | Activity heatmap data |
| GET | `/api/analytics/score-history/{user_id}` | Score history |
| GET | `/api/analytics/patterns/{user_id}` | Detected patterns |
| GET | `/api/targets` | List all targets |
| POST | `/api/targets` | Add new target |
| DELETE | `/api/targets/{user_id}` | Remove target |
| GET | `/api/targets/{user_id}/profile` | Target profile |
| GET | `/api/reports` | List reports |
| GET | `/api/reports/{user_id}/pdf` | Download PDF report |
| GET | `/api/reports/daily` | Today's summary |
| WS | `/ws/realtime` | WebSocket real-time feed |

## Deployment

For production deployment, use the provided Docker configuration:

```bash
# Build and start in background
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f app

# Stop
docker-compose down
```

For systemd-based deployment, reference the `deploy.sh` script in the teleexport project root.

## Testing

```bash
cd anti_stalker_pro
python -m pytest tests/ -v
```

## License

Private project - not for redistribution.
