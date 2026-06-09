"""Telethon-based Telegram userbot client with session management.

Provides a singleton TelethonClient with auto-reconnect, FloodWaitError
handling, and rate limiting for all Telegram API calls.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

SESSIONS_DIR = Path(__file__).parent.parent / "data" / "sessions"


class TelethonClient:
    """Singleton Telegram userbot client with rate limiting and auto-reconnect.

    Manages the Telethon session, handles FloodWaitError by sleeping,
    and enforces a minimum interval between API requests.
    """

    _instance: Optional["TelethonClient"] = None
    _client: Optional[TelegramClient] = None
    _last_request_time: float = 0.0
    _min_request_interval: float = 1.0
    _connected: bool = False

    def __new__(cls) -> "TelethonClient":
        """Ensure singleton pattern for the client instance.

        Returns:
            TelethonClient: The single client instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the client configuration from settings."""
        if self._client is not None:
            return
        settings = get_settings()
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_path = str(SESSIONS_DIR / "userbot")
        self._client = TelegramClient(
            session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        self._my_id: int = settings.my_telegram_id

    @property
    def client(self) -> TelegramClient:
        """Get the underlying TelegramClient instance.

        Returns:
            TelegramClient: The Telethon client.
        """
        return self._client

    @property
    def my_id(self) -> int:
        """Get the authenticated user's Telegram ID.

        Returns:
            int: The user's Telegram numeric ID.
        """
        return self._my_id

    @property
    def is_connected(self) -> bool:
        """Check if the client is currently connected.

        Returns:
            bool: True if connected to Telegram.
        """
        return self._connected

    async def connect(self) -> None:
        """Connect to Telegram with auto-reconnect and FloodWaitError handling.

        Starts the client session and authenticates using the phone number
        from settings. Retries on FloodWaitError by sleeping the required time.

        Raises:
            TelegramConnectionError: If connection fails after retries.
        """
        from core.exceptions import TelegramConnectionError

        settings = get_settings()
        max_retries = 3

        for attempt in range(max_retries):
            try:
                await self._client.start(phone=settings.telegram_phone)
                self._connected = True
                me = await self._client.get_me()
                logger.info(
                    f"Connected to Telegram as {me.first_name} (ID: {me.id})"
                )
                return
            except FloodWaitError as e:
                logger.warning(
                    f"FloodWaitError on connect: sleeping {e.seconds}s"
                )
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(
                    f"Connection attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if attempt == max_retries - 1:
                    raise TelegramConnectionError(
                        f"Failed to connect after {max_retries} attempts: {e}"
                    )
                await asyncio.sleep(5)

    async def disconnect(self) -> None:
        """Disconnect from Telegram gracefully.

        Closes the client session and resets connection state.
        """
        if self._client and self._connected:
            await self._client.disconnect()
            self._connected = False
            logger.info("Disconnected from Telegram")

    async def rate_limit(self) -> None:
        """Enforce minimum interval between API requests.

        Sleeps if the time since the last request is less than
        the configured minimum interval (1 second).
        """
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    async def safe_request(self, coro):
        """Execute a Telegram API request with rate limiting and FloodWait handling.

        Applies rate limiting before the request and handles FloodWaitError
        by sleeping and retrying.

        Args:
            coro: An awaitable Telegram API call.

        Returns:
            The result of the API call.

        Raises:
            Exception: Re-raises non-FloodWait exceptions after logging.
        """
        await self.rate_limit()
        try:
            result = await coro
            return result
        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s before retry")
            await asyncio.sleep(e.seconds)
            self._last_request_time = time.time()
            return await coro
        except Exception as e:
            logger.error(f"Telegram API request failed: {e}")
            raise

    async def ensure_connected(self) -> None:
        """Ensure the client is connected, reconnecting if necessary.

        Checks the connection state and reconnects if disconnected.
        """
        if not self._connected or not self._client.is_connected():
            logger.info("Client disconnected, attempting reconnect...")
            await self.connect()
