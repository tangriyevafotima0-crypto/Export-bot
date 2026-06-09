"""Reports API routes for the dashboard.

Provides endpoints for listing reports, generating PDFs,
and fetching daily summary data.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from core.database import get_session
from core.logger import get_logger
from core.models import DailyReport, TrackedUser

from dashboard.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(user: dict = Depends(get_current_user)) -> dict:
    """List all daily reports.

    Returns reports ordered by date descending.
    """
    async for session in get_session():
        result = await session.execute(
            select(DailyReport).order_by(DailyReport.report_date.desc()).limit(30)
        )
        reports = result.scalars().all()

    return {
        "reports": [
            {
                "id": r.id,
                "report_date": r.report_date,
                "total_events": r.total_events,
                "total_alerts": r.total_alerts,
                "top_suspects": r.top_suspects,
                "summary": r.summary,
                "has_pdf": r.pdf_path is not None,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
        "total": len(reports),
    }


@router.get("/{user_id}/pdf")
async def generate_pdf_report(
    user_id: int, user: dict = Depends(get_current_user)
) -> FileResponse:
    """Generate and download a PDF report for a specific user.

    Args:
        user_id: Telegram user ID to generate report for.
    """
    from pathlib import Path
    from bot.report_generator import ReportGenerator

    async for session in get_session():
        result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

    generator = ReportGenerator()
    pdf_path = await generator.generate_user_report(user_id)

    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"report_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf",
    )


@router.get("/daily")
async def get_daily_summary(user: dict = Depends(get_current_user)) -> dict:
    """Get today's summary data.

    Returns aggregated stats for the current day.
    """
    from sqlalchemy import func
    from core.models import Alert, StoryView, OnlineEvent

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    async for session in get_session():
        story_count = await session.execute(
            select(func.count(StoryView.id)).where(StoryView.viewed_at >= today)
        )
        online_count = await session.execute(
            select(func.count(OnlineEvent.id)).where(OnlineEvent.went_online >= today)
        )
        alert_count = await session.execute(
            select(func.count(Alert.id)).where(Alert.created_at >= today)
        )

        alerts_result = await session.execute(
            select(Alert)
            .where(Alert.created_at >= today)
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
        recent_alerts = alerts_result.scalars().all()

        report_result = await session.execute(
            select(DailyReport)
            .where(DailyReport.report_date == today.strftime("%Y-%m-%d"))
        )
        today_report = report_result.scalar_one_or_none()

    return {
        "date": today.strftime("%Y-%m-%d"),
        "story_views": story_count.scalar() or 0,
        "online_events": online_count.scalar() or 0,
        "alerts": alert_count.scalar() or 0,
        "recent_alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "created_at": a.created_at.isoformat(),
                "is_acknowledged": a.is_acknowledged,
            }
            for a in recent_alerts
        ],
        "report_summary": today_report.summary if today_report else None,
    }
