"""Targets API routes for the dashboard.

Provides CRUD endpoints for managing tracked users (targets).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from core.database import get_session
from core.logger import get_logger
from core.models import TrackedUser

from dashboard.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/api/targets", tags=["targets"])


class AddTargetRequest(BaseModel):
    """Request body for adding a new target."""

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    notes: str | None = None


@router.get("")
async def list_targets(user: dict = Depends(get_current_user)) -> dict:
    """List all tracked targets.

    Returns all active and inactive tracked users with their scores.
    """
    async for session in get_session():
        result = await session.execute(
            select(TrackedUser).order_by(TrackedUser.suspicion_score.desc())
        )
        targets = result.scalars().all()

    return {
        "targets": [
            {
                "id": t.id,
                "telegram_id": t.telegram_id,
                "username": t.username,
                "first_name": t.first_name,
                "last_name": t.last_name,
                "suspicion_score": round(t.suspicion_score, 1),
                "is_active": t.is_active,
                "added_at": t.added_at.isoformat(),
                "notes": t.notes,
            }
            for t in targets
        ],
        "total": len(targets),
    }


@router.post("")
async def add_target(
    request: AddTargetRequest, user: dict = Depends(get_current_user)
) -> dict:
    """Add a new target to tracking.

    Args:
        request: Target data with telegram_id and optional info.
    """
    async for session in get_session():
        existing = await session.execute(
            select(TrackedUser).where(
                TrackedUser.telegram_id == request.telegram_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Target already exists")

        new_target = TrackedUser(
            telegram_id=request.telegram_id,
            username=request.username,
            first_name=request.first_name,
            last_name=request.last_name,
            notes=request.notes,
            suspicion_score=0.0,
            is_active=True,
            added_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(new_target)
        await session.commit()
        await session.refresh(new_target)

        return {
            "message": "Target added successfully",
            "target": {
                "id": new_target.id,
                "telegram_id": new_target.telegram_id,
                "username": new_target.username,
            },
        }


@router.delete("/{user_id}")
async def delete_target(user_id: int, user: dict = Depends(get_current_user)) -> dict:
    """Remove a target from tracking by telegram_id.

    Args:
        user_id: Telegram user ID of the target to remove.
    """
    async for session in get_session():
        result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

        target.is_active = False
        target.updated_at = datetime.utcnow()
        await session.commit()

    return {"message": f"Target {user_id} deactivated"}


@router.get("/{user_id}/profile")
async def get_target_profile(
    user_id: int, user: dict = Depends(get_current_user)
) -> dict:
    """Get detailed profile for a tracked user.

    Args:
        user_id: Telegram user ID of the target.
    """
    async for session in get_session():
        result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

        from sqlalchemy import func
        from core.models import StoryView, OnlineEvent, SuspicionPattern

        story_count_result = await session.execute(
            select(func.count(StoryView.id)).where(
                StoryView.tracked_user_id == target.id
            )
        )
        story_views_count = story_count_result.scalar() or 0

        online_count_result = await session.execute(
            select(func.count(OnlineEvent.id)).where(
                OnlineEvent.tracked_user_id == target.id
            )
        )
        online_events_count = online_count_result.scalar() or 0

        patterns_result = await session.execute(
            select(SuspicionPattern)
            .where(SuspicionPattern.tracked_user_id == target.id)
            .order_by(SuspicionPattern.detected_at.desc())
            .limit(10)
        )
        patterns = patterns_result.scalars().all()

    classification = "NORMAL"
    score = target.suspicion_score
    if score >= 75:
        classification = "STALKER"
    elif score >= 50:
        classification = "SUSPICIOUS"
    elif score >= 25:
        classification = "CURIOUS"

    return {
        "telegram_id": target.telegram_id,
        "username": target.username,
        "first_name": target.first_name,
        "last_name": target.last_name,
        "phone": target.phone,
        "suspicion_score": round(target.suspicion_score, 1),
        "classification": classification,
        "is_active": target.is_active,
        "added_at": target.added_at.isoformat(),
        "updated_at": target.updated_at.isoformat(),
        "notes": target.notes,
        "stats": {
            "total_story_views": story_views_count,
            "total_online_events": online_events_count,
            "patterns_detected": len(patterns),
        },
        "recent_patterns": [
            {
                "pattern_type": p.pattern_type,
                "confidence": round(p.confidence, 3),
                "detected_at": p.detected_at.isoformat(),
            }
            for p in patterns
        ],
    }
