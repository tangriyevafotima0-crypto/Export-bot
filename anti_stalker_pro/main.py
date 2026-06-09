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
from flask import Flask
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telegram.ext import ApplicationBuilder

from core.config import get_settings
from core.database import init_db
from core.logger import get_logger
from bot.handler import setup_bot_handlers
from bot.version_channel import VersionChannel
from scheduler.task_manager import TaskManager
from trapnet.flask_server import create_flask_app, set_main_loop
from userbot.client import TelethonClient

logger = get_logger(__name__)


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

    Uses the fully configured dashboard app with all routes, auth,
    and WebSocket endpoints registered.

    Args:
        settings: Application settings instance.
    """
    from dashboard.app import create_dashboard_app

    dashboard_app = create_dashboard_app()

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


async def authenticate_userbot(client, settings) -> bool:
    """Run the interactive Telethon authentication flow.

    Prompts for phone number verification code and optional 2FA password.
    This is required on first run before the service can operate headlessly.

    Args:
        client: The Telethon client instance (must be connected).
        settings: Application settings with telegram_phone.

    Returns:
        bool: True if authentication succeeded, False otherwise.
    """
    phone = settings.telegram_phone
    logger.info(f"Starting authentication for phone: {phone}")

    try:
        await client.send_code_request(phone)
        print("\n" + "=" * 50)
        print("  Telegram Authentication Required")
        print("=" * 50)
        print(f"\n  A verification code has been sent to: {phone}")
        print("  Check your Telegram app for the code.\n")

        code = input("  Enter the verification code: ").strip()
        if not code:
            logger.error("No verification code entered.")
            return False

        try:
            await client.sign_in(phone, code)
            logger.info("Authentication successful.")
            print("\n  Authentication successful!")
            return True
        except SessionPasswordNeededError:
            print("\n  Two-factor authentication is enabled.")
            password = input("  Enter your 2FA password: ").strip()
            if not password:
                logger.error("No 2FA password entered.")
                return False
            await client.sign_in(password=password)
            logger.info("Authentication with 2FA successful.")
            print("\n  Authentication with 2FA successful!")
            return True

    except FloodWaitError as e:
        logger.error(f"Flood wait during auth: must wait {e.seconds} seconds")
        print(f"\n  ERROR: Telegram rate limit. Wait {e.seconds} seconds and try again.")
        return False
    except Exception as e:
        logger.error(f"Authentication failed: {e}", exc_info=True)
        print(f"\n  ERROR: Authentication failed: {e}")
        return False


async def main() -> None:
    """Main async entry point that orchestrates all services.

    Initializes and starts:
    - Database connection and table creation
    - Telethon userbot client (with interactive auth if needed)
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

    telethon_client = TelethonClient()
    userbot = telethon_client.client

    task_manager = TaskManager()
    task_manager.init_scheduler()

    bot_app = ApplicationBuilder().token(settings.bot_token).build()

    # Use the fully configured Flask app from trapnet instead of bare Flask
    trap_app = create_flask_app()

    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_event_loop()

    shutdown_event = asyncio.Event()

    def handle_shutdown(sig, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {sig}, initiating shutdown")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    dashboard_task = None

    # Warn if using insecure default secret key
    if settings.dashboard_secret_key == "change-me-to-a-random-secret":
        logger.warning(
            "SECURITY WARNING: Using default dashboard_secret_key. "
            "Set DASHBOARD_SECRET_KEY in .env to a random secret value."
        )

    # Warn if using insecure default admin password
    if settings.admin_password == "admin":
        logger.warning(
            "SECURITY WARNING: Using default admin_password 'admin'. "
            "Set ADMIN_PASSWORD in .env to a secure password."
        )

    try:
        logger.info("Connecting Telethon userbot")
        await telethon_client.connect()

        if not await userbot.is_user_authorized():
            logger.info("Userbot not authorized. Starting authentication flow...")
            auth_success = await authenticate_userbot(userbot, settings)
            if not auth_success:
                logger.error("Authentication failed. Cannot continue.")
                await telethon_client.disconnect()
                sys.exit(1)

        logger.info("Userbot connected and authorized")

        # Register bot command handlers before starting polling
        setup_bot_handlers(bot_app)
        logger.info("Bot command handlers registered")

        task_manager.start()
        logger.info("Task scheduler started with all monitoring jobs")

        set_main_loop(loop)

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

        # Announce system start via version channel (non-blocking)
        try:
            version_channel = VersionChannel(bot=bot_app.bot)
            await version_channel.post_version_update(
                version=settings.app_version,
                changelog=["System started successfully"],
            )
        except Exception as e:
            logger.warning(f"Failed to post startup version announcement: {e}")

        await userbot.run_until_disconnected()

    except FloodWaitError as e:
        logger.error(f"Telegram flood wait: must wait {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down services")

        try:
            if bot_app.updater and bot_app.updater.running:
                await bot_app.updater.stop()
            if bot_app.running:
                await bot_app.stop()
            await bot_app.shutdown()
        except Exception as e:
            logger.warning(f"Error shutting down bot: {e}")

        # Only shutdown scheduler if it was actually started
        if task_manager.is_running:
            try:
                task_manager.stop()
            except Exception as e:
                logger.warning(f"Error shutting down scheduler: {e}")

        if dashboard_task and not dashboard_task.done():
            dashboard_task.cancel()

        try:
            await telethon_client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting userbot: {e}")

        executor.shutdown(wait=False)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
