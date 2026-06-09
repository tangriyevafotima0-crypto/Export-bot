"""Telegram bot command handler implementing all monitoring commands.

Provides 18+ commands for managing tracked users, viewing scores,
generating reports, and controlling the monitoring system. All commands
require authorization via MY_TELEGRAM_ID check.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


def setup_bot_handlers(application: Application) -> None:
    """Register all command handlers with the bot application.

    Adds all 18+ command handlers and callback query handler
    to the provided python-telegram-bot Application instance.

    Args:
        application: The python-telegram-bot Application to configure.
    """
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("remove", cmd_remove))
    application.add_handler(CommandHandler("targets", cmd_targets))
    application.add_handler(CommandHandler("score", cmd_score))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CommandHandler("pdf", cmd_pdf))
    application.add_handler(CommandHandler("heatmap", cmd_heatmap))
    application.add_handler(CommandHandler("predict", cmd_predict))
    application.add_handler(CommandHandler("top5", cmd_top5))
    application.add_handler(CommandHandler("stories", cmd_stories))
    application.add_handler(CommandHandler("patterns", cmd_patterns))
    application.add_handler(CommandHandler("alerts", cmd_alerts))
    application.add_handler(CommandHandler("settings", cmd_settings))
    application.add_handler(CommandHandler("pause", cmd_pause))
    application.add_handler(CommandHandler("resume", cmd_resume))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("dashboard", cmd_dashboard))
    application.add_handler(CommandHandler("backup", cmd_backup))
    application.add_handler(CommandHandler("version", cmd_version))
    application.add_handler(CallbackQueryHandler(handle_callback))


def _is_authorized(update: Update) -> bool:
    """Check if the user is authorized to use the bot.

    Only the owner (MY_TELEGRAM_ID) can interact with the bot.

    Args:
        update: The Telegram Update object.

    Returns:
        bool: True if the user is authorized.
    """
    settings = get_settings()
    user_id = update.effective_user.id if update.effective_user else 0
    return user_id == settings.my_telegram_id


async def _unauthorized_response(update: Update) -> None:
    """Send an unauthorized access response.

    Args:
        update: The Telegram Update object.
    """
    await update.message.reply_text("Access denied. This bot is private.")


async def cmd_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /start command - show welcome message and main menu.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from bot.keyboards import main_menu_keyboard

    text = (
        "🛡 <b>Anti-Stalker Intelligence System</b>\n\n"
        "Welcome! I monitor and analyze suspicious Telegram activity.\n\n"
        "<b>Quick Commands:</b>\n"
        "/add - Add user to tracking\n"
        "/targets - View tracked users\n"
        "/top5 - Top 5 suspects\n"
        "/status - System status\n\n"
        "Use the menu below or type /help for all commands."
    )

    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard()
    )


async def cmd_add(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /add command - add a user to the tracking list.

    Usage: /add <telegram_id_or_username> [notes]

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser

    if not context.args:
        await update.message.reply_text(
            "Usage: /add <telegram_id_or_username> [notes]\n"
            "Example: /add 123456789 Suspicious follower"
        )
        return

    target = context.args[0]
    notes = " ".join(context.args[1:]) if len(context.args) > 1 else None

    try:
        telegram_id = int(target)
        username = None
    except ValueError:
        username = target.lstrip("@")
        telegram_id = None

    settings = get_settings()

    async for session in get_session():
        active_count_result = await session.execute(
            select(TrackedUser).where(TrackedUser.is_active.is_(True))
        )
        active_count = len(active_count_result.scalars().all())

        if active_count >= settings.max_tracked_users:
            await update.message.reply_text(
                f"Maximum tracked users ({settings.max_tracked_users}) reached. "
                f"Remove a user first with /remove."
            )
            return

        if telegram_id:
            existing = await session.execute(
                select(TrackedUser).where(
                    TrackedUser.telegram_id == telegram_id
                )
            )
        else:
            existing = await session.execute(
                select(TrackedUser).where(TrackedUser.username == username)
            )

        user = existing.scalar_one_or_none()
        if user:
            if not user.is_active:
                user.is_active = True
                user.updated_at = datetime.utcnow()
                if notes:
                    user.notes = notes
                await session.commit()
                await update.message.reply_text(
                    f"Reactivated tracking for user {user.username or user.telegram_id}."
                )
            else:
                await update.message.reply_text("This user is already being tracked.")
            return

        new_user = TrackedUser(
            telegram_id=telegram_id or 0,
            username=username,
            notes=notes,
            is_active=True,
            suspicion_score=0.0,
            added_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(new_user)
        await session.commit()

    display_name = username or str(telegram_id)
    await update.message.reply_text(
        f"Added {display_name} to tracking list.\n"
        f"Monitoring will begin on the next check cycle."
    )


async def cmd_remove(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /remove command - remove a user from tracking.

    Usage: /remove <telegram_id_or_username>

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser

    if not context.args:
        await update.message.reply_text("Usage: /remove <telegram_id_or_username>")
        return

    target = context.args[0]

    async for session in get_session():
        try:
            telegram_id = int(target)
            result = await session.execute(
                select(TrackedUser).where(
                    TrackedUser.telegram_id == telegram_id
                )
            )
        except ValueError:
            username = target.lstrip("@")
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.username == username)
            )

        user = result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("User not found in tracking list.")
            return

        user.is_active = False
        user.updated_at = datetime.utcnow()
        await session.commit()

    await update.message.reply_text(
        f"Removed {target} from active tracking. Historical data retained."
    )


async def cmd_targets(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /targets command - list all tracked users.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser

    async for session in get_session():
        result = await session.execute(
            select(TrackedUser)
            .where(TrackedUser.is_active.is_(True))
            .order_by(TrackedUser.suspicion_score.desc())
        )
        targets = result.scalars().all()

    if not targets:
        await update.message.reply_text("No users being tracked. Use /add to start.")
        return

    text = "🎯 <b>Tracked Users</b>\n\n"
    for i, t in enumerate(targets, 1):
        name = t.username or str(t.telegram_id)
        score_emoji = _score_emoji(t.suspicion_score)
        text += f"{i}. {score_emoji} <b>{name}</b> - {t.suspicion_score:.1f}/100\n"

    text += f"\n<i>Total: {len(targets)} targets</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_score(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /score command - show detailed score for a user.

    Usage: /score <telegram_id_or_username>

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from intelligence.ml_scorer import StalkerScorer

    if not context.args:
        await update.message.reply_text("Usage: /score <telegram_id_or_username>")
        return

    target = context.args[0]
    try:
        user_id = int(target)
    except ValueError:
        await update.message.reply_text("Please provide a numeric Telegram ID.")
        return

    scorer = StalkerScorer()
    explanation = await scorer.explain_score(user_id)

    if not explanation.get("breakdown"):
        await update.message.reply_text(f"No score data for user {user_id}.")
        return

    score = explanation["total_score"]
    classification = explanation["classification"]
    score_emoji = _score_emoji(score)

    text = (
        f"{score_emoji} <b>Score: {score:.1f}/100</b> ({classification})\n\n"
        f"<b>Feature Breakdown:</b>\n"
    )

    for item in explanation["breakdown"][:8]:
        bar = _mini_bar(item["raw_value"])
        text += f"  {bar} {item['feature']}: {item['contribution']:.1f}%\n"

    top = explanation.get("top_factor", "")
    if top:
        text += f"\n<b>Top Factor:</b> {top}"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /report command - show text summary report for a user.

    Usage: /report <telegram_id>

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select, func
    from core.database import get_session
    from core.models import TrackedUser, StoryView, OnlineEvent, Alert

    if not context.args:
        await update.message.reply_text("Usage: /report <telegram_id>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a numeric Telegram ID.")
        return

    async for session in get_session():
        result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        tracked = result.scalar_one_or_none()
        if not tracked:
            await update.message.reply_text(f"User {user_id} not found in tracking list.")
            return

        views_count = await session.execute(
            select(func.count(StoryView.id)).where(
                StoryView.tracked_user_id == tracked.id
            )
        )
        total_views = views_count.scalar() or 0

        events_count = await session.execute(
            select(func.count(OnlineEvent.id)).where(
                OnlineEvent.tracked_user_id == tracked.id
            )
        )
        total_events = events_count.scalar() or 0

        alerts_count = await session.execute(
            select(func.count(Alert.id)).where(
                Alert.tracked_user_id == tracked.id
            )
        )
        total_alerts = alerts_count.scalar() or 0

    name = tracked.username or str(tracked.telegram_id)
    score = tracked.suspicion_score
    text = (
        f"📋 <b>Report: {name}</b>\n\n"
        f"<b>Score:</b> {score:.1f}/100 ({_classify(score)})\n"
        f"<b>Story Views:</b> {total_views}\n"
        f"<b>Online Events:</b> {total_events}\n"
        f"<b>Alerts:</b> {total_alerts}\n"
        f"<b>Tracking Since:</b> {tracked.added_at.strftime('%Y-%m-%d')}\n"
        f"<b>Status:</b> {'Active' if tracked.is_active else 'Paused'}\n"
    )
    if tracked.notes:
        text += f"<b>Notes:</b> {tracked.notes}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_pdf(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /pdf command - generate and send a PDF report.

    Usage: /pdf <telegram_id> or /pdf daily

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from bot.report_generator import ReportGenerator

    if not context.args:
        await update.message.reply_text("Usage: /pdf <telegram_id> or /pdf daily")
        return

    await update.message.reply_text("Generating PDF report...")

    generator = ReportGenerator()

    if context.args[0].lower() == "daily":
        pdf_path = await generator.generate_daily_summary()
    else:
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Please provide a numeric Telegram ID or 'daily'.")
            return
        pdf_path = await generator.generate_user_report(user_id)

    try:
        with open(pdf_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file, caption="Generated Report"
            )
    except Exception as e:
        logger.error(f"Failed to send PDF: {e}")
        await update.message.reply_text(f"Report generated at: {pdf_path}")


async def cmd_heatmap(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /heatmap command - show activity heatmap for a user.

    Usage: /heatmap <telegram_id>

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from datetime import timedelta
    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser, StoryView, OnlineEvent

    if not context.args:
        await update.message.reply_text("Usage: /heatmap <telegram_id>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a numeric Telegram ID.")
        return

    cutoff = datetime.utcnow() - timedelta(days=14)

    async for session in get_session():
        result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        tracked = result.scalar_one_or_none()
        if not tracked:
            await update.message.reply_text(f"User {user_id} not tracked.")
            return

        views_result = await session.execute(
            select(StoryView.viewed_at).where(
                StoryView.tracked_user_id == tracked.id,
                StoryView.viewed_at >= cutoff,
            )
        )
        view_times = views_result.scalars().all()

        events_result = await session.execute(
            select(OnlineEvent.went_online).where(
                OnlineEvent.tracked_user_id == tracked.id,
                OnlineEvent.went_online >= cutoff,
            )
        )
        online_times = events_result.scalars().all()

    all_times = list(view_times) + list(online_times)
    if not all_times:
        await update.message.reply_text("No activity data for heatmap.")
        return

    grid = [[0] * 24 for _ in range(7)]
    for t in all_times:
        grid[t.weekday()][t.hour] += 1

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    max_val = max(max(row) for row in grid) or 1

    text = f"🗓 <b>Activity Heatmap: {tracked.username or user_id}</b>\n\n"
    text += "<code>     00  03  06  09  12  15  18  21\n"

    for d_idx, day in enumerate(days):
        text += f"{day}  "
        for h in range(0, 24, 3):
            total = sum(grid[d_idx][h:h + 3])
            intensity = total / max_val if max_val > 0 else 0
            if intensity == 0:
                text += " .  "
            elif intensity < 0.3:
                text += " +  "
            elif intensity < 0.6:
                text += " #  "
            else:
                text += " @  "
        text += "\n"

    text += "</code>\n<i>. = none, + = low, # = medium, @ = high</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_predict(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /predict command - show predictions for a user.

    Usage: /predict <telegram_id>

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from intelligence.predictor import Predictor

    if not context.args:
        await update.message.reply_text("Usage: /predict <telegram_id>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a numeric Telegram ID.")
        return

    predictor = Predictor()
    visit_pred = await predictor.predict_next_visit(user_id)
    online_pred = await predictor.predict_online_time(user_id)

    text = f"🔮 <b>Predictions for {user_id}</b>\n\n"

    text += "<b>Next Visit Prediction:</b>\n"
    if visit_pred.get("predicted_time"):
        text += f"  Time: {visit_pred['predicted_time']}\n"
        text += f"  Confidence: {visit_pred['confidence_percent']}%\n"
        text += f"  Method: {visit_pred['method']}\n"
    else:
        text += "  Insufficient data\n"

    text += "\n<b>Online Prediction (next 2h):</b>\n"
    text += f"  Probability: {online_pred['probability'] * 100:.1f}%\n"
    text += f"  Will be online: {'Yes' if online_pred['will_be_online'] else 'No'}\n"
    if online_pred.get("expected_at"):
        text += f"  Expected at: {online_pred['expected_at']}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_top5(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /top5 command - show top 5 most suspicious users.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser

    async for session in get_session():
        result = await session.execute(
            select(TrackedUser)
            .where(TrackedUser.is_active.is_(True))
            .order_by(TrackedUser.suspicion_score.desc())
            .limit(5)
        )
        top_users = result.scalars().all()

    if not top_users:
        await update.message.reply_text("No tracked users yet.")
        return

    text = "🏆 <b>Top 5 Suspects</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4.", "5."]

    for i, user in enumerate(top_users):
        name = user.username or str(user.telegram_id)
        score = user.suspicion_score
        classification = _classify(score)
        text += (
            f"{medals[i]} <b>{name}</b>\n"
            f"   Score: {score:.1f}/100 ({classification})\n\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_stories(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /stories command - show recent story view activity.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from datetime import timedelta
    from sqlalchemy import select, desc
    from core.database import get_session
    from core.models import StoryView, TrackedUser

    cutoff = datetime.utcnow() - timedelta(hours=24)

    async for session in get_session():
        result = await session.execute(
            select(StoryView, TrackedUser)
            .join(TrackedUser, StoryView.tracked_user_id == TrackedUser.id)
            .where(StoryView.viewed_at >= cutoff)
            .order_by(desc(StoryView.viewed_at))
            .limit(20)
        )
        rows = result.all()

    if not rows:
        await update.message.reply_text("No story views in the last 24 hours.")
        return

    text = "👁 <b>Recent Story Views (24h)</b>\n\n"
    for view, user in rows:
        name = user.username or str(user.telegram_id)
        time_str = view.viewed_at.strftime("%H:%M")
        position = f"#{view.view_order}" if view.view_order else ""
        text += f"  {time_str} - <b>{name}</b> {position}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_patterns(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /patterns command - show detected patterns.

    Usage: /patterns [telegram_id]

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select, desc
    from core.database import get_session
    from core.models import SuspicionPattern, TrackedUser

    async for session in get_session():
        if context.args:
            try:
                user_id = int(context.args[0])
            except ValueError:
                await update.message.reply_text("Please provide a numeric Telegram ID.")
                return

            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                await update.message.reply_text(f"User {user_id} not tracked.")
                return

            patterns_result = await session.execute(
                select(SuspicionPattern)
                .where(SuspicionPattern.tracked_user_id == tracked.id)
                .order_by(desc(SuspicionPattern.detected_at))
                .limit(10)
            )
        else:
            patterns_result = await session.execute(
                select(SuspicionPattern)
                .order_by(desc(SuspicionPattern.detected_at))
                .limit(15)
            )

        patterns = patterns_result.scalars().all()

    if not patterns:
        await update.message.reply_text("No patterns detected yet.")
        return

    text = "🕵️ <b>Detected Patterns</b>\n\n"
    for p in patterns:
        confidence_pct = p.confidence * 100
        text += (
            f"  <b>{p.pattern_type}</b>\n"
            f"  Confidence: {confidence_pct:.0f}% | "
            f"{p.detected_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_alerts(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /alerts command - show recent alerts.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from bot.alert_manager import AlertManager

    manager = AlertManager()
    alerts = await manager.get_recent_alerts(limit=10)

    if not alerts:
        await update.message.reply_text("No alerts yet.")
        return

    text = "🚨 <b>Recent Alerts</b>\n\n"
    for alert in alerts:
        emoji = _severity_emoji(alert.severity)
        ack = "✓" if alert.is_acknowledged else "○"
        text += (
            f"{ack} {emoji} <b>{alert.alert_type}</b>\n"
            f"   {alert.message[:80]}\n"
            f"   {alert.created_at.strftime('%m-%d %H:%M')}\n\n"
        )

    unack_count = await manager.get_unacknowledged_count()
    text += f"<i>Pending: {unack_count} unacknowledged</i>"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /settings command - show current configuration.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from bot.keyboards import settings_keyboard

    settings = get_settings()
    text = (
        "⚙️ <b>Current Settings</b>\n\n"
        f"<b>Online Check Interval:</b> {settings.online_check_interval}s\n"
        f"<b>Story Check Interval:</b> {settings.story_check_interval}s\n"
        f"<b>Analysis Interval:</b> {settings.analysis_interval}s\n"
        f"<b>Alert Threshold:</b> {settings.alert_threshold}/100\n"
        f"<b>Max Tracked Users:</b> {settings.max_tracked_users}\n"
        f"<b>Log Level:</b> {settings.log_level}\n"
        f"<b>Trap Server:</b> {settings.trap_server_host}:{settings.trap_server_port}\n"
        f"<b>Dashboard:</b> {settings.dashboard_host}:{settings.dashboard_port}\n"
    )

    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=settings_keyboard()
    )


async def cmd_pause(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /pause command - pause monitoring for a user or all.

    Usage: /pause [telegram_id] (omit to pause all)

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser

    async for session in get_session():
        if context.args:
            try:
                user_id = int(context.args[0])
            except ValueError:
                await update.message.reply_text("Please provide a numeric Telegram ID.")
                return

            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_active = False
                user.updated_at = datetime.utcnow()
                await session.commit()
                await update.message.reply_text(
                    f"Paused monitoring for {user.username or user_id}."
                )
            else:
                await update.message.reply_text("User not found.")
        else:
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            users = result.scalars().all()
            for user in users:
                user.is_active = False
                user.updated_at = datetime.utcnow()
            await session.commit()
            await update.message.reply_text(
                f"Paused monitoring for all {len(users)} users."
            )


async def cmd_resume(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /resume command - resume monitoring for a user or all.

    Usage: /resume [telegram_id] (omit to resume all)

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select
    from core.database import get_session
    from core.models import TrackedUser

    async for session in get_session():
        if context.args:
            try:
                user_id = int(context.args[0])
            except ValueError:
                await update.message.reply_text("Please provide a numeric Telegram ID.")
                return

            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_active = True
                user.updated_at = datetime.utcnow()
                await session.commit()
                await update.message.reply_text(
                    f"Resumed monitoring for {user.username or user_id}."
                )
            else:
                await update.message.reply_text("User not found.")
        else:
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(False))
            )
            users = result.scalars().all()
            for user in users:
                user.is_active = True
                user.updated_at = datetime.utcnow()
            await session.commit()
            await update.message.reply_text(
                f"Resumed monitoring for {len(users)} users."
            )


async def cmd_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /status command - show system status overview.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    from sqlalchemy import select, func
    from core.database import get_session
    from core.models import TrackedUser, StoryView, OnlineEvent, Alert

    async for session in get_session():
        active_count = await session.execute(
            select(func.count(TrackedUser.id)).where(
                TrackedUser.is_active.is_(True)
            )
        )
        total_active = active_count.scalar() or 0

        total_views = await session.execute(
            select(func.count(StoryView.id))
        )
        views_count = total_views.scalar() or 0

        total_events = await session.execute(
            select(func.count(OnlineEvent.id))
        )
        events_count = total_events.scalar() or 0

        pending_alerts = await session.execute(
            select(func.count(Alert.id)).where(
                Alert.is_acknowledged.is_(False)
            )
        )
        pending_count = pending_alerts.scalar() or 0

    settings = get_settings()
    text = (
        "📋 <b>System Status</b>\n\n"
        f"🟢 <b>Status:</b> Running\n"
        f"🎯 <b>Active Targets:</b> {total_active}/{settings.max_tracked_users}\n"
        f"👁 <b>Total Story Views:</b> {views_count}\n"
        f"📡 <b>Total Online Events:</b> {events_count}\n"
        f"🚨 <b>Pending Alerts:</b> {pending_count}\n"
        f"⏱ <b>Uptime:</b> Active\n"
        f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_dashboard(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /dashboard command - show dashboard access information.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    settings = get_settings()
    text = (
        "📊 <b>Dashboard Access</b>\n\n"
        f"<b>URL:</b> http://{settings.dashboard_host}:{settings.dashboard_port}\n"
        f"<b>Status:</b> Running\n\n"
        "Open the dashboard in your browser for a full interactive view "
        "of monitoring data, charts, and management tools."
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_backup(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /backup command - create and send a database backup.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db_path = DATA_DIR / "anti_stalker.db"
    backup_path = backup_dir / f"backup_{timestamp}.db"

    if db_path.exists():
        shutil.copy2(str(db_path), str(backup_path))
        try:
            with open(backup_path, "rb") as backup_file:
                await update.message.reply_document(
                    document=backup_file,
                    caption=f"Database backup: {timestamp}",
                )
        except Exception as e:
            logger.error(f"Failed to send backup: {e}")
            await update.message.reply_text(
                f"Backup saved to: {backup_path}"
            )
    else:
        await update.message.reply_text(
            "Database file not found. System may be using a new database."
        )


async def cmd_version(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /version command - show current application version.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    if not _is_authorized(update):
        await _unauthorized_response(update)
        return

    settings = get_settings()
    text = (
        "📦 <b>Version Information</b>\n\n"
        f"<b>Version:</b> {settings.app_version}\n"
        f"<b>System:</b> Anti-Stalker Intelligence System\n"
        f"<b>Status:</b> Running\n"
        f"<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline keyboard callback queries.

    Routes callback data to appropriate handlers based on prefix.

    Args:
        update: The Telegram Update object.
        context: The callback context.
    """
    query = update.callback_query
    if not query:
        return

    if not _is_authorized(update):
        await query.answer("Access denied.")
        return

    await query.answer()
    data = query.data

    if data == "main_menu":
        from bot.keyboards import main_menu_keyboard
        await query.edit_message_text(
            "🛡 <b>Anti-Stalker Intelligence System</b>\n\nSelect an option:",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )
    elif data == "menu_scores":
        await query.edit_message_text(
            "📊 Use /score <telegram_id> to view a user's score.\n"
            "Use /top5 to see the top suspects.",
            parse_mode=ParseMode.HTML,
        )
    elif data == "menu_stories":
        await query.edit_message_text(
            "👁 Use /stories to see recent story views.",
            parse_mode=ParseMode.HTML,
        )
    elif data == "menu_targets":
        await query.edit_message_text(
            "🎯 Use /targets to list all tracked users.\n"
            "Use /add to add a new target.",
            parse_mode=ParseMode.HTML,
        )
    elif data == "menu_alerts":
        from bot.keyboards import alert_level_keyboard
        await query.edit_message_text(
            "🚨 <b>Alert Filters</b>\n\nSelect severity level:",
            parse_mode=ParseMode.HTML,
            reply_markup=alert_level_keyboard(),
        )
    elif data == "menu_reports":
        await query.edit_message_text(
            "📈 Use /report <id> for text report.\n"
            "Use /pdf <id> for PDF report.\n"
            "Use /pdf daily for daily summary.",
            parse_mode=ParseMode.HTML,
        )
    elif data == "menu_predict":
        await query.edit_message_text(
            "🔮 Use /predict <telegram_id> to see predictions.",
            parse_mode=ParseMode.HTML,
        )
    elif data == "menu_settings":
        from bot.keyboards import settings_keyboard
        settings = get_settings()
        text = (
            "⚙️ <b>Settings</b>\n\n"
            f"Alert Threshold: {settings.alert_threshold}\n"
            f"Max Targets: {settings.max_tracked_users}\n"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=settings_keyboard()
        )
    elif data == "menu_status":
        await query.edit_message_text(
            "📋 Use /status for full system status.",
            parse_mode=ParseMode.HTML,
        )
    elif data == "cancel_action":
        await query.edit_message_text("Action cancelled.")
    elif data == "noop":
        pass
    else:
        await query.edit_message_text(
            f"Action: {data}\nUse the corresponding command for full functionality.",
        )


def _score_emoji(score: float) -> str:
    """Get an emoji representation for a suspicion score.

    Args:
        score: Suspicion score from 0 to 100.

    Returns:
        str: Colored circle emoji indicating severity.
    """
    if score < 25:
        return "🟢"
    elif score < 50:
        return "🟡"
    elif score < 75:
        return "🟠"
    else:
        return "🔴"


def _severity_emoji(severity: str) -> str:
    """Get an emoji for an alert severity level.

    Args:
        severity: Severity string.

    Returns:
        str: Corresponding emoji.
    """
    mapping = {
        "info": "🔵",
        "warning": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }
    return mapping.get(severity.lower(), "⚪")


def _classify(score: float) -> str:
    """Classify a score into a risk category label.

    Args:
        score: Suspicion score from 0 to 100.

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


def _mini_bar(value: float) -> str:
    """Generate a mini progress bar for inline display.

    Args:
        value: Value from 0.0 to 1.0.

    Returns:
        str: Short visual bar string.
    """
    filled = int(value * 5)
    empty = 5 - filled
    return "▓" * filled + "░" * empty
