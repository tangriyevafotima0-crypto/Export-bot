"""Main entry point for the Anti-Stalker Intelligence System.

Orchestrates all services: Telethon userbot, python-telegram-bot,
Flask trap server, FastAPI dashboard, and APScheduler.
"""

import asyncio
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telegram.ext import ApplicationBuilder

from core.config import get_settings
from core.database import init_db
from core.logger import get_logger

logger = get_logger(__name__)


def create_trap_server(settings) -> Flask:
    """Create and configure the Flask trap server application.

    Args:
        settings: Application settings instance.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.dashboard_secret_key
    return app


def run_trap_server(app: Flask, host: str, port: int) -> None:
    """Run the Flask trap server in a thread.

    Args:
        app: Flask application instance.
        host: Host to bind to.
        port: Port to listen on.
    """
    app.run(host=host, port=port, debug=False, use_reloader=False)


async def run_dashboard(settings) -> None:
    """Start the FastAPI dashboard server.

    Args:
        settings: Application settings instance.
    """
    from fastapi import FastAPI

    dashboard_app = FastAPI(title="Anti-Stalker Dashboard")

    config = uvicorn.Config(
        dashboard_app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def send_startup_notification(bot_app, chat_id: int) -> None:
    """Send a startup notification via the Telegram bot.

    Args:
        bot_app: The python-telegram-bot Application instance.
        chat_id: Telegram chat ID to send notification to.
    """
    try:
        await bot_app.bot.send_message(
            chat_id=chat_id,
            text="Anti-Stalker Intelligence System started successfully.",
        )
    except Exception as e:
        logger.warning(f"Failed to send startup notification: {e}")


async def main() -> None:
    """Main async entry point that orchestrates all services.

    Initializes and starts:
    - Database connection and table creation
    - Telethon userbot client
    - APScheduler for periodic tasks
    - Flask trap server (in thread executor)
    - FastAPI dashboard server
    - python-telegram-bot polling
    - Startup notification
    """
    settings = get_settings()
    logger.info("Starting Anti-Stalker Intelligence System")

    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    logger.info("Initializing database")
    await init_db()
    logger.info("Database initialized successfully")

    userbot = TelegramClient(
        str(data_dir / "userbot_session"),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    scheduler = AsyncIOScheduler()

    bot_app = ApplicationBuilder().token(settings.bot_token).build()

    trap_app = create_trap_server(settings)

    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_event_loop()

    shutdown_event = asyncio.Event()

    def handle_shutdown(sig, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {sig}, initiating shutdown")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        logger.info("Connecting Telethon userbot")
        await userbot.connect()

        if not await userbot.is_user_authorized():
            logger.error(
                "Userbot not authorized. Run authentication flow first."
            )
            await userbot.disconnect()
            sys.exit(1)

        logger.info("Userbot connected and authorized")

        scheduler.start()
        logger.info("APScheduler started")

        loop.run_in_executor(
            executor,
            run_trap_server,
            trap_app,
            settings.trap_server_host,
            settings.trap_server_port,
        )
        logger.info(
            f"Flask trap server started on "
            f"{settings.trap_server_host}:{settings.trap_server_port}"
        )

        dashboard_task = asyncio.create_task(run_dashboard(settings))
        logger.info(
            f"FastAPI dashboard started on "
            f"{settings.dashboard_host}:{settings.dashboard_port}"
        )

        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Telegram bot polling started")

        await send_startup_notification(bot_app, settings.my_telegram_id)
        logger.info("System fully operational")

        await userbot.run_until_disconnected()

    except FloodWaitError as e:
        logger.error(f"Telegram flood wait: must wait {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down services")

        if bot_app.updater and bot_app.updater.running:
            await bot_app.updater.stop()
        if bot_app.running:
            await bot_app.stop()
        await bot_app.shutdown()

        scheduler.shutdown(wait=False)

        if dashboard_task and not dashboard_task.done():
            dashboard_task.cancel()

        await userbot.disconnect()

        executor.shutdown(wait=False)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
