"""PDF report generator using ReportLab for detailed monitoring reports.

Creates professional PDF reports with cover pages, score summaries,
story view tables, online timeline tables, heatmap visualizations,
score history graphs, and pattern analysis sections.
"""

import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.graphics.widgets.markers import makeMarker
from sqlalchemy import select, func, desc

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import (
    Alert,
    DailyReport,
    OnlineEvent,
    StoryView,
    SuspicionPattern,
    TrackedUser,
)

logger = get_logger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "data" / "reports"


class ReportGenerator:
    """Generates detailed PDF reports using ReportLab.

    Creates multi-page PDF documents with professional formatting
    including cover pages, data tables, charts, and visualizations.
    """

    def __init__(self) -> None:
        """Initialize the ReportGenerator with output directory and styles."""
        self._settings = get_settings()
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self) -> None:
        """Add custom paragraph styles for report formatting."""
        self._styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self._styles["Title"],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor("#1a1a2e"),
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self._styles["Heading2"],
                fontSize=14,
                spaceBefore=20,
                spaceAfter=10,
                textColor=colors.HexColor("#16213e"),
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="ReportBody",
                parent=self._styles["Normal"],
                fontSize=10,
                leading=14,
            )
        )

    async def generate_user_report(self, user_id: int) -> str:
        """Generate a full PDF report for a specific tracked user.

        Creates a multi-page report with cover page, score summary,
        story view table, online timeline, heatmap visualization,
        score history graph, and pattern analysis.

        Args:
            user_id: Telegram user ID to generate report for.

        Returns:
            str: File path to the generated PDF report.
        """
        data = await self._gather_user_data(user_id)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"user_report_{user_id}_{timestamp}.pdf"
        filepath = REPORTS_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []
        elements.extend(self._build_cover_page(data))
        elements.append(PageBreak())
        elements.extend(self._build_score_summary(data))
        elements.append(Spacer(1, 20))
        elements.extend(self._build_story_view_table(data))
        elements.append(PageBreak())
        elements.extend(self._build_online_timeline(data))
        elements.append(Spacer(1, 20))
        elements.extend(self._build_heatmap(data))
        elements.append(PageBreak())
        elements.extend(self._build_score_history_graph(data))
        elements.append(Spacer(1, 20))
        elements.extend(self._build_pattern_analysis(data))

        doc.build(elements)
        logger.info(f"User report generated: {filepath}")
        return str(filepath)

    async def generate_daily_summary(self) -> str:
        """Generate a daily overview PDF report summarizing all activity.

        Creates a report covering the last 24 hours with event counts,
        alert summary, top suspects, and activity overview.

        Returns:
            str: File path to the generated PDF report.
        """
        data = await self._gather_daily_data()
        date_str = datetime.utcnow().strftime("%Y%m%d")
        filename = f"daily_report_{date_str}.pdf"
        filepath = REPORTS_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        elements.append(
            Paragraph(
                "Daily Monitoring Summary",
                self._styles["ReportTitle"],
            )
        )
        elements.append(
            Paragraph(
                f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                self._styles["ReportBody"],
            )
        )
        elements.append(Spacer(1, 30))

        elements.append(
            Paragraph("Overview", self._styles["SectionHeader"])
        )
        overview_data = [
            ["Metric", "Value"],
            ["Total Story Views", str(data.get("total_story_views", 0))],
            ["Total Online Events", str(data.get("total_online_events", 0))],
            ["Alerts Generated", str(data.get("total_alerts", 0))],
            ["Active Targets", str(data.get("active_targets", 0))],
        ]
        overview_table = Table(overview_data, colWidths=[250, 200])
        overview_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f0f0f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(overview_table)
        elements.append(Spacer(1, 20))

        elements.append(
            Paragraph("Top Suspects", self._styles["SectionHeader"])
        )
        suspects_data = [["User", "Score", "Classification"]]
        for suspect in data.get("top_suspects", [])[:10]:
            classification = self._classify_score(suspect["score"])
            suspects_data.append(
                [
                    suspect.get("username", str(suspect.get("telegram_id", "?"))),
                    f"{suspect['score']:.1f}",
                    classification,
                ]
            )

        if len(suspects_data) > 1:
            suspects_table = Table(suspects_data, colWidths=[180, 100, 150])
            suspects_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
                    ]
                )
            )
            elements.append(suspects_table)
        else:
            elements.append(
                Paragraph("No suspects tracked today.", self._styles["ReportBody"])
            )

        elements.append(Spacer(1, 20))

        elements.append(
            Paragraph("Alert Summary", self._styles["SectionHeader"])
        )
        alert_summary = data.get("alert_summary", {})
        alert_data = [["Severity", "Count"]]
        for severity in ["critical", "high", "warning", "info"]:
            count = alert_summary.get(severity, 0)
            alert_data.append([severity.upper(), str(count)])

        alert_table = Table(alert_data, colWidths=[200, 150])
        alert_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(alert_table)

        doc.build(elements)
        logger.info(f"Daily summary report generated: {filepath}")

        await self._store_daily_report(data, str(filepath))

        return str(filepath)

    def _build_cover_page(self, data: dict) -> list:
        """Build the cover page elements for a user report.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for the cover page.
        """
        elements = []
        elements.append(Spacer(1, 100))
        elements.append(
            Paragraph(
                "Anti-Stalker Intelligence Report",
                self._styles["ReportTitle"],
            )
        )
        elements.append(Spacer(1, 30))

        user_info = data.get("user", {})
        username = user_info.get("username", "Unknown")
        telegram_id = user_info.get("telegram_id", "N/A")
        score = user_info.get("suspicion_score", 0)
        classification = self._classify_score(score)

        elements.append(
            Paragraph(
                f"<b>Subject:</b> {username} (ID: {telegram_id})",
                self._styles["ReportBody"],
            )
        )
        elements.append(
            Paragraph(
                f"<b>Suspicion Score:</b> {score:.1f}/100 ({classification})",
                self._styles["ReportBody"],
            )
        )
        elements.append(
            Paragraph(
                f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                self._styles["ReportBody"],
            )
        )
        elements.append(
            Paragraph(
                f"<b>Monitoring Since:</b> {user_info.get('added_at', 'N/A')}",
                self._styles["ReportBody"],
            )
        )
        return elements

    def _build_score_summary(self, data: dict) -> list:
        """Build the score summary section.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for score summary.
        """
        elements = []
        elements.append(
            Paragraph("Score Summary", self._styles["SectionHeader"])
        )

        user_info = data.get("user", {})
        score = user_info.get("suspicion_score", 0)
        classification = self._classify_score(score)

        score_data = [
            ["Metric", "Value"],
            ["Current Score", f"{score:.1f}/100"],
            ["Classification", classification],
            ["Total Story Views", str(data.get("total_story_views", 0))],
            ["Total Online Events", str(data.get("total_online_events", 0))],
            ["Patterns Detected", str(data.get("total_patterns", 0))],
            ["Alerts Generated", str(data.get("total_alerts", 0))],
        ]

        table = Table(score_data, colWidths=[250, 200])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f0f0f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        return elements

    def _build_story_view_table(self, data: dict) -> list:
        """Build the story view history table section.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for story views table.
        """
        elements = []
        elements.append(
            Paragraph("Story View History", self._styles["SectionHeader"])
        )

        views = data.get("story_views", [])
        if not views:
            elements.append(
                Paragraph("No story views recorded.", self._styles["ReportBody"])
            )
            return elements

        table_data = [["Date/Time", "Story ID", "View Position", "Reaction"]]
        for view in views[:30]:
            table_data.append(
                [
                    view["viewed_at"],
                    str(view["story_id"]),
                    str(view.get("view_order", "-")),
                    view.get("reaction", "-") or "-",
                ]
            )

        table = Table(table_data, colWidths=[150, 80, 100, 100])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
                ]
            )
        )
        elements.append(table)
        return elements

    def _build_online_timeline(self, data: dict) -> list:
        """Build the online timeline table section.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for online timeline.
        """
        elements = []
        elements.append(
            Paragraph("Online Activity Timeline", self._styles["SectionHeader"])
        )

        events = data.get("online_events", [])
        if not events:
            elements.append(
                Paragraph("No online events recorded.", self._styles["ReportBody"])
            )
            return elements

        table_data = [["Went Online", "Went Offline", "Duration", "Overlaps"]]
        for event in events[:30]:
            duration = event.get("duration_seconds")
            duration_str = f"{duration // 60}m {duration % 60}s" if duration else "-"
            table_data.append(
                [
                    event["went_online"],
                    event.get("went_offline", "-") or "-",
                    duration_str,
                    "Yes" if event.get("overlaps_with_me") else "No",
                ]
            )

        table = Table(table_data, colWidths=[130, 130, 80, 80])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
                ]
            )
        )
        elements.append(table)
        return elements

    def _build_heatmap(self, data: dict) -> list:
        """Build a heatmap visualization of activity by hour and weekday.

        Creates a table-based heatmap showing activity density
        across hours of the day and days of the week.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for the heatmap.
        """
        elements = []
        elements.append(
            Paragraph(
                "Activity Heatmap (Hour x Weekday)", self._styles["SectionHeader"]
            )
        )

        heatmap_data = data.get("heatmap", {})
        if not heatmap_data:
            elements.append(
                Paragraph("Insufficient data for heatmap.", self._styles["ReportBody"])
            )
            return elements

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hours_range = range(0, 24, 3)
        header = [""] + [f"{h:02d}" for h in hours_range]
        table_data = [header]

        max_val = max(
            (heatmap_data.get(f"{d}_{h}", 0) for d in range(7) for h in hours_range),
            default=1,
        ) or 1

        for d_idx, day_name in enumerate(days):
            row = [day_name]
            for h in hours_range:
                val = heatmap_data.get(f"{d_idx}_{h}", 0)
                row.append(str(val) if val > 0 else ".")
            table_data.append(row)

        col_widths = [40] + [40] * len(list(hours_range))
        table = Table(table_data, colWidths=col_widths)

        style_commands = [
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]

        for d_idx in range(7):
            for h_idx, h in enumerate(hours_range):
                val = heatmap_data.get(f"{d_idx}_{h}", 0)
                intensity = min(1.0, val / max_val) if max_val > 0 else 0
                bg_color = colors.Color(
                    1.0 - intensity * 0.7,
                    1.0 - intensity * 0.3,
                    1.0 - intensity * 0.7,
                )
                style_commands.append(
                    ("BACKGROUND", (h_idx + 1, d_idx + 1), (h_idx + 1, d_idx + 1), bg_color)
                )

        table.setStyle(TableStyle(style_commands))
        elements.append(table)
        return elements

    def _build_score_history_graph(self, data: dict) -> list:
        """Build a score history line graph.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for the score graph.
        """
        elements = []
        elements.append(
            Paragraph("Score History", self._styles["SectionHeader"])
        )

        history = data.get("score_history", [])
        if len(history) < 2:
            elements.append(
                Paragraph(
                    "Insufficient data for score graph.",
                    self._styles["ReportBody"],
                )
            )
            return elements

        drawing = Drawing(450, 200)
        lp = LinePlot()
        lp.x = 50
        lp.y = 30
        lp.width = 380
        lp.height = 150

        plot_data = [(i, entry["score"]) for i, entry in enumerate(history[-30:])]
        lp.data = [plot_data]
        lp.lines[0].strokeColor = colors.HexColor("#e94560")
        lp.lines[0].strokeWidth = 2

        lp.xValueAxis.valueMin = 0
        lp.xValueAxis.valueMax = len(plot_data) - 1
        lp.yValueAxis.valueMin = 0
        lp.yValueAxis.valueMax = 100
        lp.yValueAxis.valueStep = 20

        drawing.add(lp)
        elements.append(drawing)
        return elements

    def _build_pattern_analysis(self, data: dict) -> list:
        """Build the pattern analysis section.

        Args:
            data: User report data dictionary.

        Returns:
            list: ReportLab flowable elements for pattern analysis.
        """
        elements = []
        elements.append(
            Paragraph("Pattern Analysis", self._styles["SectionHeader"])
        )

        patterns = data.get("patterns", [])
        if not patterns:
            elements.append(
                Paragraph("No patterns detected.", self._styles["ReportBody"])
            )
            return elements

        table_data = [["Pattern Type", "Confidence", "Detected At"]]
        for pattern in patterns[:20]:
            table_data.append(
                [
                    pattern["pattern_type"],
                    f"{pattern['confidence'] * 100:.1f}%",
                    pattern["detected_at"],
                ]
            )

        table = Table(table_data, colWidths=[180, 100, 150])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
                ]
            )
        )
        elements.append(table)
        return elements

    async def _gather_user_data(self, user_id: int) -> dict:
        """Gather all data needed for a user report from the database.

        Args:
            user_id: Telegram user ID to gather data for.

        Returns:
            dict: Comprehensive data dictionary for report generation.
        """
        data = {}
        cutoff = datetime.utcnow() - timedelta(days=30)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return {"user": {"telegram_id": user_id, "username": "Unknown"}}

            data["user"] = {
                "telegram_id": tracked.telegram_id,
                "username": tracked.username or str(tracked.telegram_id),
                "first_name": tracked.first_name,
                "suspicion_score": tracked.suspicion_score,
                "added_at": tracked.added_at.strftime("%Y-%m-%d"),
                "is_active": tracked.is_active,
            }

            views_result = await session.execute(
                select(StoryView)
                .where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
                .order_by(desc(StoryView.viewed_at))
            )
            views = views_result.scalars().all()
            data["story_views"] = [
                {
                    "story_id": v.story_id,
                    "viewed_at": v.viewed_at.strftime("%Y-%m-%d %H:%M"),
                    "view_order": v.view_order,
                    "reaction": v.reaction,
                }
                for v in views
            ]
            data["total_story_views"] = len(views)

            events_result = await session.execute(
                select(OnlineEvent)
                .where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
                .order_by(desc(OnlineEvent.went_online))
            )
            events = events_result.scalars().all()
            data["online_events"] = [
                {
                    "went_online": e.went_online.strftime("%Y-%m-%d %H:%M"),
                    "went_offline": e.went_offline.strftime("%Y-%m-%d %H:%M") if e.went_offline else None,
                    "duration_seconds": e.duration_seconds,
                    "overlaps_with_me": e.overlaps_with_me,
                }
                for e in events
            ]
            data["total_online_events"] = len(events)

            patterns_result = await session.execute(
                select(SuspicionPattern)
                .where(SuspicionPattern.tracked_user_id == tracked.id)
                .order_by(desc(SuspicionPattern.detected_at))
            )
            patterns = patterns_result.scalars().all()
            data["patterns"] = [
                {
                    "pattern_type": p.pattern_type,
                    "confidence": p.confidence,
                    "detected_at": p.detected_at.strftime("%Y-%m-%d %H:%M"),
                }
                for p in patterns
            ]
            data["total_patterns"] = len(patterns)

            alerts_result = await session.execute(
                select(func.count(Alert.id)).where(
                    Alert.tracked_user_id == tracked.id
                )
            )
            data["total_alerts"] = alerts_result.scalar() or 0

            heatmap = {}
            for v in views:
                key = f"{v.viewed_at.weekday()}_{(v.viewed_at.hour // 3) * 3}"
                heatmap[key] = heatmap.get(key, 0) + 1
            for e in events:
                key = f"{e.went_online.weekday()}_{(e.went_online.hour // 3) * 3}"
                heatmap[key] = heatmap.get(key, 0) + 1
            data["heatmap"] = heatmap

            data["score_history"] = [
                {"date": p.detected_at.strftime("%Y-%m-%d"), "score": p.confidence * 100}
                for p in sorted(patterns, key=lambda x: x.detected_at)
            ]

        return data

    async def _gather_daily_data(self) -> dict:
        """Gather all data needed for the daily summary report.

        Returns:
            dict: Daily report data dictionary.
        """
        data = {}
        cutoff = datetime.utcnow() - timedelta(hours=24)

        async for session in get_session():
            views_count = await session.execute(
                select(func.count(StoryView.id)).where(
                    StoryView.viewed_at >= cutoff
                )
            )
            data["total_story_views"] = views_count.scalar() or 0

            events_count = await session.execute(
                select(func.count(OnlineEvent.id)).where(
                    OnlineEvent.went_online >= cutoff
                )
            )
            data["total_online_events"] = events_count.scalar() or 0

            alerts_result = await session.execute(
                select(Alert).where(Alert.created_at >= cutoff)
            )
            alerts = alerts_result.scalars().all()
            data["total_alerts"] = len(alerts)

            alert_summary = {}
            for alert in alerts:
                sev = alert.severity.lower()
                alert_summary[sev] = alert_summary.get(sev, 0) + 1
            data["alert_summary"] = alert_summary

            targets_result = await session.execute(
                select(TrackedUser)
                .where(TrackedUser.is_active.is_(True))
                .order_by(desc(TrackedUser.suspicion_score))
            )
            targets = targets_result.scalars().all()
            data["active_targets"] = len(targets)
            data["top_suspects"] = [
                {
                    "telegram_id": t.telegram_id,
                    "username": t.username or str(t.telegram_id),
                    "score": t.suspicion_score,
                }
                for t in targets[:10]
            ]

        return data

    async def _store_daily_report(self, data: dict, pdf_path: str) -> None:
        """Store the daily report record in the database.

        Args:
            data: Daily report data dictionary.
            pdf_path: Path to the generated PDF file.
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")

        async for session in get_session():
            existing = await session.execute(
                select(DailyReport).where(DailyReport.report_date == today)
            )
            report = existing.scalar_one_or_none()

            top_suspects_dict = {
                s.get("username", str(s.get("telegram_id"))): s["score"]
                for s in data.get("top_suspects", [])[:5]
            }

            if report:
                report.total_events = data.get("total_story_views", 0) + data.get("total_online_events", 0)
                report.total_alerts = data.get("total_alerts", 0)
                report.top_suspects = top_suspects_dict
                report.pdf_path = pdf_path
            else:
                report = DailyReport(
                    report_date=today,
                    total_events=data.get("total_story_views", 0) + data.get("total_online_events", 0),
                    total_alerts=data.get("total_alerts", 0),
                    top_suspects=top_suspects_dict,
                    pdf_path=pdf_path,
                )
                session.add(report)

            await session.commit()

    def _classify_score(self, score: float) -> str:
        """Classify a numeric score into a risk category.

        Args:
            score: Numeric score from 0 to 100.

        Returns:
            str: Classification label.
        """
        if score < 25:
            return "NORMAL"
        elif score < 50:
            return "CURIOUS"
        elif score < 75:
            return "SUSPICIOUS"
        else:
            return "STALKER"
