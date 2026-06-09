"""Inline keyboard builders for the Telegram bot interface.

Provides pre-built InlineKeyboardMarkup objects for all interactive
menus, confirmation dialogs, and navigation flows.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard.

    Displays primary action categories with emoji labels.

    Returns:
        InlineKeyboardMarkup: Main menu keyboard layout.
    """
    keyboard = [
        [
            InlineKeyboardButton("📊 Scores", callback_data="menu_scores"),
            InlineKeyboardButton("👁 Stories", callback_data="menu_stories"),
        ],
        [
            InlineKeyboardButton("🎯 Targets", callback_data="menu_targets"),
            InlineKeyboardButton("🚨 Alerts", callback_data="menu_alerts"),
        ],
        [
            InlineKeyboardButton("📈 Reports", callback_data="menu_reports"),
            InlineKeyboardButton("🔮 Predict", callback_data="menu_predict"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            InlineKeyboardButton("📋 Status", callback_data="menu_status"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def target_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Build the action keyboard for a specific tracked target.

    Provides options to view details, score, report, or remove.

    Args:
        user_id: Telegram user ID for callback data.

    Returns:
        InlineKeyboardMarkup: Target action keyboard.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Score", callback_data=f"target_score_{user_id}"
            ),
            InlineKeyboardButton(
                "📄 Report", callback_data=f"target_report_{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔮 Predict", callback_data=f"target_predict_{user_id}"
            ),
            InlineKeyboardButton(
                "🕵️ Patterns", callback_data=f"target_patterns_{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏸ Pause", callback_data=f"target_pause_{user_id}"
            ),
            InlineKeyboardButton(
                "❌ Remove", callback_data=f"target_remove_{user_id}"
            ),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="menu_targets"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def alert_level_keyboard() -> InlineKeyboardMarkup:
    """Build the alert level filter keyboard.

    Allows filtering alerts by severity level.

    Returns:
        InlineKeyboardMarkup: Alert level selection keyboard.
    """
    keyboard = [
        [
            InlineKeyboardButton("🔴 CRITICAL", callback_data="alert_critical"),
            InlineKeyboardButton("🟠 HIGH", callback_data="alert_high"),
        ],
        [
            InlineKeyboardButton("🟡 WARNING", callback_data="alert_warning"),
            InlineKeyboardButton("🔵 INFO", callback_data="alert_info"),
        ],
        [
            InlineKeyboardButton("📋 All Alerts", callback_data="alert_all"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def settings_keyboard() -> InlineKeyboardMarkup:
    """Build the settings configuration keyboard.

    Provides access to monitoring interval, threshold, and
    notification settings.

    Returns:
        InlineKeyboardMarkup: Settings keyboard layout.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "⏱ Intervals", callback_data="settings_intervals"
            ),
            InlineKeyboardButton(
                "🎚 Thresholds", callback_data="settings_thresholds"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔔 Notifications", callback_data="settings_notifications"
            ),
            InlineKeyboardButton(
                "🌙 Quiet Hours", callback_data="settings_quiet_hours"
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Max Targets", callback_data="settings_max_targets"
            ),
            InlineKeyboardButton(
                "🗄 Database", callback_data="settings_database"
            ),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Build a confirmation dialog keyboard.

    Used for destructive actions that require user confirmation.

    Args:
        action: The action identifier to confirm (e.g., "remove_123").

    Returns:
        InlineKeyboardMarkup: Yes/No confirmation keyboard.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Yes, confirm", callback_data=f"confirm_{action}"
            ),
            InlineKeyboardButton(
                "❌ Cancel", callback_data="cancel_action"
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def pagination_keyboard(
    current_page: int, total_pages: int, prefix: str
) -> InlineKeyboardMarkup:
    """Build a pagination keyboard for multi-page results.

    Args:
        current_page: Current page number (1-indexed).
        total_pages: Total number of pages.
        prefix: Callback data prefix for page navigation.

    Returns:
        InlineKeyboardMarkup: Pagination navigation keyboard.
    """
    buttons = []
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                "◀️ Prev", callback_data=f"{prefix}_page_{current_page - 1}"
            )
        )
    buttons.append(
        InlineKeyboardButton(
            f"{current_page}/{total_pages}", callback_data="noop"
        )
    )
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                "Next ▶️", callback_data=f"{prefix}_page_{current_page + 1}"
            )
        )

    keyboard = [buttons]
    keyboard.append(
        [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]
    )
    return InlineKeyboardMarkup(keyboard)
