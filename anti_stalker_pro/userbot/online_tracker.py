"""Online status tracking module for monitored users.

Monitors online/offline transitions for tracked users and records
events with duration calculations in the OnlineEvent table.
"""

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from telethon.errors import FloodWaitError
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import UserStatusOnline, UserStatusOffline

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import OnlineEvent, TrackedUser

logger = get_logger(__name__)


class OnlineTracker:
    """Tracks online/offline status changes for monitored users.

    Records transitions between online and offline states, calculates
    session durations, and detects overlap with the owner's activity.
    """

    _instance: Optional["OnlineTracker"] = None

    def __new__(cls) -> "OnlineTracker":
        """Ensure singleton pattern for the tracker instance.

        Returns:
            OnlineTracker: The single tracker instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the OnlineTracker with the userbot client."""
        if hasattr(self, "_online_cache"):
            return
        from userbot.client import TelethonClient

        self._telethon = TelethonClient()
        self._settings = get_settings()
        self._online_cache: dict[int, datetime] = {}

    async def check_all_targets(self) -> int:
        """Check online status of all active tracked users.

        Fetches the full user info for each tracked user and records
        online/offline transitions in the database.

        Returns:
            int: Number of status changes detected.
        """
        await self._telethon.ensure_connected()
        changes = 0

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = result.scalars().all()

        for user in tracked_users:
            try:
                changed = await self._check_user_status(user)
                if changed:
                    changes += 1
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(
                    f"FloodWaitError checking user {user.telegram_id}: "
                    f"sleeping {e.seconds}s"
                )
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(
                    f"Error checking status for user {user.telegram_id}: {e}"
                )

        if changes > 0:
            logger.info(f"Detected {changes} online status changes")
        return changes

    async def _check_user_status(self, tracked_user: TrackedUser) -> bool:
        """Check and record online status for a single tracked user.

        Args:
            tracked_user: The TrackedUser record to check.

        Returns:
            bool: True if a status change was detected and recorded.
        """
        client = self._telethon.client
        user_id = tracked_user.telegram_id

        try:
            full_user = await self._telethon.safe_request(
                client(GetFullUserRequest(user_id))
            )
        except Exception as e:
            logger.debug(f"Cannot get full user for {user_id}: {e}")
            return False

        user = full_user.users[0] if full_user.users else None
        if user is None:
            return False

        status = user.status
        now = datetime.utcnow()

        if isinstance(status, UserStatusOnline):
            return await self._handle_online(tracked_user, now)
        elif isinstance(status, UserStatusOffline):
            return await self._handle_offline(tracked_user, now, status)

        return False

    async def _handle_online(
        self, tracked_user: TrackedUser, now: datetime
    ) -> bool:
        """Handle a user transitioning to online status.

        Args:
            tracked_user: The tracked user record.
            now: Current UTC timestamp.

        Returns:
            bool: True if this is a new online event.
        """
        user_id = tracked_user.telegram_id

        if user_id in self._online_cache:
            return False

        self._online_cache[user_id] = now
        logger.debug(f"User {user_id} came online at {now}")

        owner_online = await self._check_owner_online()

        async for session in get_session():
            event = OnlineEvent(
                tracked_user_id=tracked_user.id,
                went_online=now,
                went_offline=None,
                duration_seconds=None,
                overlaps_with_me=owner_online,
            )
            session.add(event)
            await session.commit()

        return True

    async def _handle_offline(
        self,
        tracked_user: TrackedUser,
        now: datetime,
        status: UserStatusOffline,
    ) -> bool:
        """Handle a user transitioning to offline status.

        Calculates the duration of the online session and updates
        the most recent OnlineEvent record.

        Args:
            tracked_user: The tracked user record.
            now: Current UTC timestamp.
            status: The offline status with was_online timestamp.

        Returns:
            bool: True if an offline transition was recorded.
        """
        user_id = tracked_user.telegram_id

        if user_id not in self._online_cache:
            return False

        went_online = self._online_cache.pop(user_id)
        offline_time = status.was_online if status.was_online else now
        duration = int((offline_time - went_online).total_seconds())

        if duration < 0:
            duration = 0

        async for session in get_session():
            result = await session.execute(
                select(OnlineEvent)
                .where(
                    OnlineEvent.tracked_user_id == tracked_user.id,
                    OnlineEvent.went_offline.is_(None),
                )
                .order_by(OnlineEvent.went_online.desc())
                .limit(1)
            )
            event = result.scalar_one_or_none()
            if event:
                event.went_offline = offline_time
                event.duration_seconds = duration
                await session.commit()

        logger.debug(
            f"User {user_id} went offline after {duration}s"
        )
        return True

    async def _check_owner_online(self) -> bool:
        """Check if the bot owner is currently online.

        Returns:
            bool: True if the owner is currently online.
        """
        client = self._telethon.client
        try:
            me = await client.get_me()
            return isinstance(getattr(me, "status", None), UserStatusOnline)
        except Exception:
            return False

    async def get_online_history(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """Get online event history for a tracked user.

        Args:
            user_id: The Telegram user ID.
            days: Number of days to look back.

        Returns:
            list[dict]: List of online events with timestamps and durations.
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(
                    TrackedUser.telegram_id == user_id
                )
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return []

            events_result = await session.execute(
                select(OnlineEvent)
                .where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
                .order_by(OnlineEvent.went_online.desc())
            )
            events = events_result.scalars().all()

            return [
                {
                    "went_online": e.went_online.isoformat(),
                    "went_offline": e.went_offline.isoformat() if e.went_offline else None,
                    "duration_seconds": e.duration_seconds,
                    "overlaps_with_me": e.overlaps_with_me,
                }
                for e in events
            ]
