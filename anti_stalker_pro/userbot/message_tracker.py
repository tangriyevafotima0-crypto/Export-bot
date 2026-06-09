"""Message tracking module for detecting read-without-reply and forwarding patterns.

Monitors read receipts, identifies users who read messages without replying,
and detects forwarding patterns of the owner's content.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetMessagesViewsRequest

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import TrackedUser, SuspicionPattern

logger = get_logger(__name__)


class MessageTracker:
    """Tracks message read receipts and forwarding patterns.

    Monitors who reads messages without replying and identifies users
    who forward the owner's content, both of which are stalking indicators.
    """

    def __init__(self) -> None:
        """Initialize the MessageTracker with the userbot client."""
        from userbot.client import TelethonClient

        self._telethon = TelethonClient()
        self._settings = get_settings()
        self._read_counts: dict[int, dict] = {}

    async def track_read_receipts(self) -> dict[int, dict]:
        """Monitor who reads messages without replying.

        Iterates over recent direct message conversations with tracked users,
        counts read-but-not-replied messages, and returns statistics.

        Returns:
            dict[int, dict]: Mapping of user_id to read receipt statistics
                with keys: total_sent, total_read, total_replied, ratio.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        results: dict[int, dict] = {}

        async for session in get_session():
            tracked_result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = tracked_result.scalars().all()

        for tracked_user in tracked_users:
            try:
                stats = await self._analyze_conversation(
                    tracked_user.telegram_id
                )
                if stats:
                    results[tracked_user.telegram_id] = stats
                    self._read_counts[tracked_user.telegram_id] = stats
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(
                    f"FloodWaitError tracking reads: sleeping {e.seconds}s"
                )
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(
                    f"Error tracking reads for {tracked_user.telegram_id}: {e}"
                )

        return results

    async def _analyze_conversation(self, user_id: int) -> Optional[dict]:
        """Analyze a conversation for read-without-reply patterns.

        Examines recent messages in a direct conversation to determine
        how many sent messages were read but not replied to.

        Args:
            user_id: The Telegram user ID to analyze conversation with.

        Returns:
            Optional[dict]: Conversation statistics or None if no data.
        """
        client = self._telethon.client
        total_sent = 0
        total_replied = 0
        my_messages = []
        their_messages = []

        try:
            async for message in client.iter_messages(user_id, limit=100):
                if message.out:
                    total_sent += 1
                    my_messages.append(message)
                else:
                    their_messages.append(message)
                await asyncio.sleep(0.05)

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return None
        except Exception as e:
            logger.debug(f"Cannot analyze conversation with {user_id}: {e}")
            return None

        if total_sent == 0:
            return None

        for their_msg in their_messages:
            if their_msg.reply_to and their_msg.reply_to.reply_to_msg_id:
                for my_msg in my_messages:
                    if my_msg.id == their_msg.reply_to.reply_to_msg_id:
                        total_replied += 1
                        break

        total_read = total_sent
        ratio = (total_sent - total_replied) / total_sent if total_sent > 0 else 0.0

        return {
            "total_sent": total_sent,
            "total_read": total_read,
            "total_replied": total_replied,
            "read_without_reply": total_sent - total_replied,
            "ratio": round(ratio, 3),
        }

    async def detect_forward_patterns(self) -> list[dict]:
        """Identify users who forward the owner's content.

        Searches global message forwards to find instances where tracked
        users have forwarded the owner's messages to other chats.

        Returns:
            list[dict]: List of forward events with user_id, message_id,
                and forward details.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        forwards = []
        my_id = self._telethon.my_id

        async for session in get_session():
            tracked_result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = {
                u.telegram_id: u for u in tracked_result.scalars().all()
            }

        for user_id, tracked_user in tracked_users.items():
            try:
                async for message in client.iter_messages(user_id, limit=50):
                    if (
                        message.forward
                        and hasattr(message.forward, "from_id")
                        and message.forward.from_id
                    ):
                        from_id = getattr(message.forward.from_id, "user_id", None)
                        if from_id == my_id:
                            forwards.append({
                                "user_id": user_id,
                                "username": tracked_user.username,
                                "message_id": message.id,
                                "forwarded_at": message.date.isoformat(),
                                "original_date": (
                                    message.forward.date.isoformat()
                                    if message.forward.date
                                    else None
                                ),
                            })
                    await asyncio.sleep(0.05)
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.debug(f"Cannot check forwards for {user_id}: {e}")

        if forwards:
            logger.info(f"Detected {len(forwards)} forward events from tracked users")
        return forwards

    async def calculate_read_without_reply_ratio(self, user_id: int) -> float:
        """Calculate the read-without-reply ratio for a specific user.

        A high ratio indicates the user reads messages consistently but
        rarely replies, which can be a stalking indicator.

        Args:
            user_id: The Telegram user ID to calculate ratio for.

        Returns:
            float: Ratio between 0.0 (always replies) and 1.0 (never replies).
        """
        if user_id in self._read_counts:
            return self._read_counts[user_id].get("ratio", 0.0)

        stats = await self._analyze_conversation(user_id)
        if stats:
            self._read_counts[user_id] = stats
            return stats["ratio"]

        return 0.0
