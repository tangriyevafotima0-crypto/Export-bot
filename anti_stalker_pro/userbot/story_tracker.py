"""Story tracking module for monitoring who views stories.

Tracks story views by users, detects suspicious viewing patterns,
and records data in the StoryView database table.
"""

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from telethon.errors import FloodWaitError
from telethon.tl.functions.stories import GetAllStoriesRequest, GetStoryViewsListRequest
from telethon.tl.functions.users import GetFullUserRequest

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import Alert, StoryView, TrackedUser

logger = get_logger(__name__)


class StoryTracker:
    """Tracks story views and identifies suspicious viewers.

    Monitors who views stories, records view events in the database,
    and triggers alerts when tracked users are detected as viewers.
    """

    def __init__(self) -> None:
        """Initialize the StoryTracker with the userbot client."""
        from userbot.client import TelethonClient

        self._telethon = TelethonClient()
        self._settings = get_settings()

    async def check_all_stories(self) -> int:
        """Check all current stories for views by tracked users.

        Iterates through active stories, fetches viewer lists,
        and records new views by tracked users in the database.

        Returns:
            int: Number of new suspicious views detected.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        new_views = 0

        try:
            stories_result = await self._telethon.safe_request(
                client(GetAllStoriesRequest(next=""))
            )

            if not stories_result or not hasattr(stories_result, "peer_stories"):
                logger.debug("No stories found to check")
                return 0

            for peer_story in stories_result.peer_stories:
                for story in peer_story.stories:
                    views_count = await self._process_story_viewers(story.id)
                    new_views += views_count
                    await asyncio.sleep(1)

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError in check_all_stories: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error checking stories: {e}")

        if new_views > 0:
            logger.info(f"Detected {new_views} new suspicious story views")
        return new_views

    async def _process_story_viewers(self, story_id: int) -> int:
        """Process viewers for a specific story and record tracked user views.

        Args:
            story_id: The story ID to check viewers for.

        Returns:
            int: Number of new tracked user views found.
        """
        client = self._telethon.client
        new_views = 0

        try:
            viewers_result = await self._telethon.safe_request(
                client(GetStoryViewsListRequest(
                    peer=await client.get_me(),
                    id=story_id,
                    offset_date=0,
                    offset_id=0,
                    limit=100,
                    q="",
                ))
            )

            if not viewers_result or not hasattr(viewers_result, "views"):
                return 0

            async for session in get_session():
                tracked_result = await session.execute(
                    select(TrackedUser).where(TrackedUser.is_active.is_(True))
                )
                tracked_users = {
                    u.telegram_id: u for u in tracked_result.scalars().all()
                }

                for idx, view in enumerate(viewers_result.views):
                    viewer_id = view.user_id
                    if viewer_id in tracked_users:
                        existing = await session.execute(
                            select(StoryView).where(
                                StoryView.tracked_user_id == tracked_users[viewer_id].id,
                                StoryView.story_id == story_id,
                            )
                        )
                        if existing.scalar_one_or_none() is None:
                            story_view = StoryView(
                                tracked_user_id=tracked_users[viewer_id].id,
                                story_id=story_id,
                                viewed_at=datetime.utcnow(),
                                view_order=idx + 1,
                                reaction=getattr(view, "reaction", None),
                            )
                            session.add(story_view)
                            new_views += 1

                            await self._check_alert_threshold(
                                session, tracked_users[viewer_id]
                            )

                await session.commit()

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError getting story viewers: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error processing story {story_id} viewers: {e}")

        return new_views

    async def _check_alert_threshold(
        self, session, tracked_user: TrackedUser
    ) -> None:
        """Check if a tracked user's activity warrants an alert.

        Args:
            session: Active database session.
            tracked_user: The tracked user to evaluate.
        """
        if tracked_user.suspicion_score >= self._settings.alert_threshold:
            alert = Alert(
                tracked_user_id=tracked_user.id,
                alert_type="story_view",
                severity="high",
                message=(
                    f"Suspicious user {tracked_user.username or tracked_user.telegram_id} "
                    f"viewed your story (score: {tracked_user.suspicion_score:.1f})"
                ),
                details={"score": tracked_user.suspicion_score},
            )
            session.add(alert)

    async def get_story_viewers(self, story_id: int) -> list[dict]:
        """Get all viewers for a specific story.

        Args:
            story_id: The story ID to fetch viewers for.

        Returns:
            list[dict]: List of viewer info dictionaries with user_id,
                view_order, and reaction fields.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        viewers = []

        try:
            viewers_result = await self._telethon.safe_request(
                client(GetStoryViewsListRequest(
                    peer=await client.get_me(),
                    id=story_id,
                    offset_date=0,
                    offset_id=0,
                    limit=100,
                    q="",
                ))
            )

            if viewers_result and hasattr(viewers_result, "views"):
                for idx, view in enumerate(viewers_result.views):
                    viewers.append({
                        "user_id": view.user_id,
                        "view_order": idx + 1,
                        "reaction": getattr(view, "reaction", None),
                    })

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error getting story viewers: {e}")

        return viewers

    async def get_my_story_viewers(self) -> list[dict]:
        """Get viewers across all of my active stories.

        Returns:
            list[dict]: Combined list of viewers from all active stories,
                each with story_id, user_id, view_order, and reaction.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        all_viewers = []

        try:
            stories_result = await self._telethon.safe_request(
                client(GetAllStoriesRequest(next=""))
            )

            if not stories_result or not hasattr(stories_result, "peer_stories"):
                return []

            for peer_story in stories_result.peer_stories:
                for story in peer_story.stories:
                    viewers = await self.get_story_viewers(story.id)
                    for viewer in viewers:
                        viewer["story_id"] = story.id
                    all_viewers.extend(viewers)
                    await asyncio.sleep(1)

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error getting all story viewers: {e}")

        return all_viewers
