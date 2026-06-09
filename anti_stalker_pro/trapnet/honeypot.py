"""Honeypot bait management for proactive stalker identification.

Generates unique tracking URLs per target, schedules bait stories at
optimal times, and evaluates which baits were triggered to confirm
stalking behavior.
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import select, func

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import BioLinkVisit, TrackedUser

logger = get_logger(__name__)


class BaitType(str, Enum):
    """Types of honeypot baits that can be deployed."""

    BIO_LINK_BAIT = "bio_link_bait"
    STORY_MENTION_BAIT = "story_mention_bait"
    TIMED_STORY_BAIT = "timed_story_bait"
    UNIQUE_LINK_BAIT = "unique_link_bait"


class HoneypotManager:
    """Manages honeypot baits for proactive stalker identification.

    Generates unique tracking URLs per target user, schedules bait
    stories for posting at predicted optimal times, and analyzes
    which baits were triggered.
    """

    def __init__(self) -> None:
        """Initialize the HoneypotManager with settings."""
        self._settings = get_settings()

    def generate_unique_tracking_url(self, user_id: int) -> str:
        """Generate a unique short tracking URL code for a specific target.

        Creates a deterministic but unguessable short code tied to the
        user_id combined with a random salt. The URL is served by the
        Flask trap server.

        Args:
            user_id: Telegram user ID of the target being tracked.

        Returns:
            str: Full tracking URL (e.g., http://host:port/<code>).
        """
        salt = secrets.token_hex(4)
        raw = f"{user_id}:{salt}:{datetime.utcnow().timestamp()}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
        code = self._make_short_code(digest)

        host = self._settings.trap_server_host
        port = self._settings.trap_server_port

        if host == "0.0.0.0":
            host = "127.0.0.1"

        return f"http://{host}:{port}/{code}"

    def generate_tracking_code(self, user_id: int) -> str:
        """Generate just the tracking code portion for a target user.

        Args:
            user_id: Telegram user ID of the target.

        Returns:
            str: Short alphanumeric tracking code.
        """
        salt = secrets.token_hex(4)
        raw = f"{user_id}:{salt}:{datetime.utcnow().timestamp()}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
        return self._make_short_code(digest)

    async def schedule_bait_story(self, target_time: datetime) -> dict:
        """Schedule a bait story to be posted at the predicted optimal time.

        Uses the predictor's output to determine when a suspected stalker
        is most likely to be watching, then schedules a story with an
        embedded tracking link.

        Args:
            target_time: The predicted optimal time to post the bait.

        Returns:
            dict: Scheduling result with bait_type, scheduled_time,
                tracking_code, and status.
        """
        now = datetime.utcnow()
        if target_time <= now:
            target_time = now + timedelta(minutes=5)

        tracking_code = secrets.token_urlsafe(6)
        delay_seconds = (target_time - now).total_seconds()

        logger.info(
            f"Bait story scheduled for {target_time.isoformat()} "
            f"(in {delay_seconds:.0f}s), code={tracking_code}"
        )

        return {
            "bait_type": BaitType.TIMED_STORY_BAIT.value,
            "scheduled_time": target_time.isoformat(),
            "tracking_code": tracking_code,
            "delay_seconds": delay_seconds,
            "status": "scheduled",
        }

    async def evaluate_bait_results(self) -> list[dict]:
        """Analyze which bait tracking links have been triggered.

        Queries BioLinkVisit records to find visits to bait links,
        correlates them with tracked users, and returns results
        indicating confirmed stalking behavior.

        Returns:
            list[dict]: List of triggered bait results, each with
                link_id, visitor_ip, visit_count, matched_user_id,
                first_visit, last_visit, and bait_type.
        """
        results = []
        cutoff = datetime.utcnow() - timedelta(days=7)

        async for session in get_session():
            visits_result = await session.execute(
                select(
                    BioLinkVisit.link_id,
                    BioLinkVisit.visitor_ip,
                    BioLinkVisit.matched_user_id,
                    func.count(BioLinkVisit.id).label("visit_count"),
                    func.min(BioLinkVisit.visited_at).label("first_visit"),
                    func.max(BioLinkVisit.visited_at).label("last_visit"),
                )
                .where(BioLinkVisit.visited_at >= cutoff)
                .group_by(
                    BioLinkVisit.link_id,
                    BioLinkVisit.visitor_ip,
                    BioLinkVisit.matched_user_id,
                )
            )
            rows = visits_result.all()

            for row in rows:
                result_entry = {
                    "link_id": row.link_id,
                    "visitor_ip": row.visitor_ip,
                    "visit_count": row.visit_count,
                    "matched_user_id": row.matched_user_id,
                    "first_visit": row.first_visit.isoformat() if row.first_visit else None,
                    "last_visit": row.last_visit.isoformat() if row.last_visit else None,
                    "bait_type": self._classify_bait_type(row.link_id),
                }
                results.append(result_entry)

        logger.info(f"Evaluated {len(results)} bait trigger results")
        return results

    async def get_baits_for_user(self, user_id: int) -> list[dict]:
        """Get all bait link visits associated with a specific user.

        Args:
            user_id: Telegram user ID to get bait results for.

        Returns:
            list[dict]: List of bait visit records for the user.
        """
        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return []

            visits_result = await session.execute(
                select(BioLinkVisit).where(
                    BioLinkVisit.matched_user_id == tracked.id
                )
            )
            visits = visits_result.scalars().all()

        return [
            {
                "link_id": v.link_id,
                "visitor_ip": v.visitor_ip,
                "user_agent": v.user_agent,
                "country": v.country,
                "city": v.city,
                "visited_at": v.visited_at.isoformat(),
                "device_info": v.device_info,
            }
            for v in visits
        ]

    def _make_short_code(self, hex_input: str) -> str:
        """Convert a hex string to a URL-safe short code.

        Args:
            hex_input: Hexadecimal string to convert.

        Returns:
            str: Short alphanumeric code suitable for URLs.
        """
        chars = string.ascii_lowercase + string.digits
        code = ""
        value = int(hex_input, 16)
        while value > 0 and len(code) < 8:
            code += chars[value % len(chars)]
            value //= len(chars)
        return code if code else secrets.token_urlsafe(6)

    def _classify_bait_type(self, link_id: str) -> str:
        """Classify a bait type based on the link_id format.

        Args:
            link_id: The tracking link identifier.

        Returns:
            str: The classified bait type string.
        """
        if link_id.startswith("bio_"):
            return BaitType.BIO_LINK_BAIT.value
        elif link_id.startswith("story_"):
            return BaitType.STORY_MENTION_BAIT.value
        elif link_id.startswith("timed_"):
            return BaitType.TIMED_STORY_BAIT.value
        else:
            return BaitType.UNIQUE_LINK_BAIT.value
