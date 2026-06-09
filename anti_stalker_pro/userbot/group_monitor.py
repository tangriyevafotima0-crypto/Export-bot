"""Group activity monitoring for detecting stalking patterns in groups.

Monitors mutual groups, tracks reactions and replies to the owner's
messages, and identifies users with consistent group interaction patterns.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetCommonChatsRequest
from telethon.tl.types import (
    MessageActionEmpty,
    PeerUser,
)

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import SuspicionPattern, TrackedUser

logger = get_logger(__name__)


class GroupMonitor:
    """Monitors group activity to detect stalking patterns.

    Scans mutual groups, watches for reactions/replies to the owner's
    messages, and identifies users who consistently interact in groups.
    """

    def __init__(self) -> None:
        """Initialize the GroupMonitor with the userbot client."""
        from userbot.client import TelethonClient

        self._telethon = TelethonClient()
        self._settings = get_settings()

    async def scan_mutual_groups(self, user_id: int) -> list[dict]:
        """Find all mutual groups shared with a specific user.

        Args:
            user_id: The Telegram user ID to check groups for.

        Returns:
            list[dict]: List of mutual group info with id, title, and members_count.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        groups = []

        try:
            result = await self._telethon.safe_request(
                client(GetCommonChatsRequest(user_id=user_id, max_id=0, limit=100))
            )

            for chat in result.chats:
                groups.append({
                    "id": chat.id,
                    "title": getattr(chat, "title", "Unknown"),
                    "members_count": getattr(chat, "participants_count", 0),
                })

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError in scan_mutual_groups: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error scanning mutual groups for {user_id}: {e}")

        return groups

    async def monitor_group_activity(self, group_id: int) -> list[dict]:
        """Watch for reactions and replies to the owner's messages in a group.

        Fetches recent messages in the group and identifies those that
        are replies to or reactions on the owner's messages.

        Args:
            group_id: The group/chat ID to monitor.

        Returns:
            list[dict]: List of interaction events with user_id, type, and timestamp.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        interactions = []
        my_id = self._telethon.my_id

        try:
            async for message in client.iter_messages(group_id, limit=200):
                await asyncio.sleep(0.1)

                if message.reply_to and message.reply_to.reply_to_msg_id:
                    try:
                        replied_msg = await client.get_messages(
                            group_id, ids=message.reply_to.reply_to_msg_id
                        )
                        if replied_msg and replied_msg.sender_id == my_id:
                            interactions.append({
                                "user_id": message.sender_id,
                                "type": "reply",
                                "message_id": message.id,
                                "timestamp": message.date.isoformat(),
                            })
                    except Exception:
                        pass

                if hasattr(message, "reactions") and message.reactions:
                    if message.sender_id == my_id:
                        for reaction_result in (message.reactions.results or []):
                            interactions.append({
                                "user_id": None,
                                "type": "reaction_to_my_msg",
                                "message_id": message.id,
                                "timestamp": message.date.isoformat(),
                                "reaction": str(reaction_result.reaction),
                            })

        except FloodWaitError as e:
            logger.warning(
                f"FloodWaitError in monitor_group_activity: sleeping {e.seconds}s"
            )
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error monitoring group {group_id}: {e}")

        return interactions

    async def detect_group_stalking_patterns(self) -> list[dict]:
        """Identify users who consistently interact with the owner across groups.

        Scans all tracked users' mutual groups and looks for patterns of
        consistent interaction (replies, reactions) with the owner's messages.
        Records detected patterns in the SuspicionPattern table.

        Returns:
            list[dict]: List of detected patterns with user_id, score, and details.
        """
        await self._telethon.ensure_connected()
        detected_patterns = []

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = result.scalars().all()

        for tracked_user in tracked_users:
            try:
                mutual_groups = await self.scan_mutual_groups(
                    tracked_user.telegram_id
                )
                if not mutual_groups:
                    continue

                total_interactions = 0
                group_interaction_counts = []

                for group in mutual_groups[:5]:
                    interactions = await self.monitor_group_activity(group["id"])
                    user_interactions = [
                        i for i in interactions
                        if i.get("user_id") == tracked_user.telegram_id
                    ]
                    total_interactions += len(user_interactions)
                    group_interaction_counts.append(len(user_interactions))
                    await asyncio.sleep(1)

                if total_interactions >= 3:
                    consistency = (
                        len([c for c in group_interaction_counts if c > 0])
                        / max(len(group_interaction_counts), 1)
                    )
                    confidence = min(1.0, total_interactions / 10.0) * consistency

                    pattern_data = {
                        "user_id": tracked_user.telegram_id,
                        "username": tracked_user.username,
                        "mutual_groups": len(mutual_groups),
                        "total_interactions": total_interactions,
                        "consistency": round(consistency, 2),
                        "confidence": round(confidence, 2),
                    }
                    detected_patterns.append(pattern_data)

                    async for session in get_session():
                        pattern = SuspicionPattern(
                            tracked_user_id=tracked_user.id,
                            pattern_type="GROUP_STALKER",
                            confidence=confidence,
                            details=pattern_data,
                            detected_at=datetime.utcnow(),
                        )
                        session.add(pattern)
                        await session.commit()

            except FloodWaitError as e:
                logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(
                    f"Error detecting patterns for {tracked_user.telegram_id}: {e}"
                )

        logger.info(f"Detected {len(detected_patterns)} group stalking patterns")
        return detected_patterns
