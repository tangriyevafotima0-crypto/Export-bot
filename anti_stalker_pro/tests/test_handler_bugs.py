"""Tests for BUG #12 (username support in /score, /predict, /report)
and BUG #14 (/help command).
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# BUG #14: /help command tests
# ===========================================================================


class TestCmdHelp:
    """Tests for the /help command."""

    @patch("bot.handler.get_settings")
    async def test_help_lists_all_commands(self, mock_settings):
        """cmd_help should send a message listing all available commands."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_help

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await cmd_help(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]

        expected_commands = [
            "/start", "/help", "/add", "/remove", "/targets",
            "/score", "/report", "/pdf", "/heatmap", "/predict",
            "/top5", "/stories", "/patterns", "/alerts", "/settings",
            "/pause", "/resume", "/status", "/dashboard", "/backup",
            "/version",
        ]
        for cmd in expected_commands:
            assert cmd in text, f"{cmd} not found in help text"

    @patch("bot.handler.get_settings")
    async def test_help_unauthorized(self, mock_settings):
        """cmd_help should deny access for unauthorized users."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_help

        update = MagicMock()
        update.effective_user.id = 999
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await cmd_help(update, context)

        update.message.reply_text.assert_called_once_with(
            "Access denied. This bot is private."
        )

    def test_help_registered_in_setup(self):
        """setup_bot_handlers should register the help command."""
        from bot.handler import setup_bot_handlers

        app = MagicMock()
        setup_bot_handlers(app)

        handler_calls = app.add_handler.call_args_list
        command_names = []
        for call in handler_calls:
            handler = call[0][0]
            if hasattr(handler, "commands"):
                command_names.extend(handler.commands)

        assert "help" in command_names


# ===========================================================================
# BUG #12: Username support in /score, /predict, /report
# ===========================================================================


class TestCmdScoreUsername:
    """Tests for /score username resolution."""

    @patch("bot.handler.get_settings")
    async def test_score_with_username_found(self, mock_settings):
        """cmd_score should resolve username and show score."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_score

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@testuser"]

        tracked_user = MagicMock()
        tracked_user.telegram_id = 456
        tracked_user.username = "testuser"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tracked_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        mock_scorer = MagicMock()
        mock_scorer.explain_score = AsyncMock(return_value={
            "total_score": 75.0,
            "classification": "SUSPICIOUS",
            "breakdown": [
                {"feature": "story_views", "raw_value": 0.8, "contribution": 40.0},
            ],
            "top_factor": "Frequent story views",
        })

        with patch("core.database.get_session", mock_get_session), \
             patch("intelligence.ml_scorer.StalkerScorer", return_value=mock_scorer):
            await cmd_score(update, context)

        # Should have called explain_score with the resolved ID
        mock_scorer.explain_score.assert_called_once_with(456)

    @patch("bot.handler.get_settings")
    async def test_score_with_username_not_found(self, mock_settings):
        """cmd_score should reply not found when username is not tracked."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_score

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@unknown"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.get_session", mock_get_session):
            await cmd_score(update, context)

        update.message.reply_text.assert_called_once_with(
            "User unknown not found in tracking list."
        )

    @patch("bot.handler.get_settings")
    async def test_score_with_username_no_telegram_id(self, mock_settings):
        """cmd_score should reply no resolved ID when telegram_id is None."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_score

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@noident"]

        tracked_user = MagicMock()
        tracked_user.telegram_id = None
        tracked_user.username = "noident"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tracked_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.get_session", mock_get_session):
            await cmd_score(update, context)

        update.message.reply_text.assert_called_once_with(
            "User noident doesn't have a resolved Telegram ID yet."
        )


class TestCmdPredictUsername:
    """Tests for /predict username resolution."""

    @patch("bot.handler.get_settings")
    async def test_predict_with_username_found(self, mock_settings):
        """cmd_predict should resolve username and show predictions."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_predict

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@testuser"]

        tracked_user = MagicMock()
        tracked_user.telegram_id = 789
        tracked_user.username = "testuser"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tracked_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        mock_predictor = MagicMock()
        mock_predictor.predict_next_visit = AsyncMock(return_value={
            "predicted_time": "14:00",
            "confidence_percent": 80,
            "method": "pattern_analysis",
        })
        mock_predictor.predict_online_time = AsyncMock(return_value={
            "probability": 0.75,
            "will_be_online": True,
            "expected_at": "14:30",
        })

        with patch("core.database.get_session", mock_get_session), \
             patch("intelligence.predictor.Predictor", return_value=mock_predictor):
            await cmd_predict(update, context)

        mock_predictor.predict_next_visit.assert_called_once_with(789)
        mock_predictor.predict_online_time.assert_called_once_with(789)

    @patch("bot.handler.get_settings")
    async def test_predict_with_username_not_found(self, mock_settings):
        """cmd_predict should reply not found when username is not tracked."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_predict

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@ghost"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.get_session", mock_get_session):
            await cmd_predict(update, context)

        update.message.reply_text.assert_called_once_with(
            "User ghost not found in tracking list."
        )

    @patch("bot.handler.get_settings")
    async def test_predict_with_username_no_telegram_id(self, mock_settings):
        """cmd_predict should reply no resolved ID when telegram_id is None."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_predict

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@noid"]

        tracked_user = MagicMock()
        tracked_user.telegram_id = None
        tracked_user.username = "noid"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tracked_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.get_session", mock_get_session):
            await cmd_predict(update, context)

        update.message.reply_text.assert_called_once_with(
            "User noid doesn't have a resolved Telegram ID yet."
        )


class TestCmdReportUsername:
    """Tests for /report username resolution."""

    @patch("bot.handler.get_settings")
    async def test_report_with_username_found(self, mock_settings):
        """cmd_report should resolve username and show report."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_report

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@suspect"]

        tracked_user_by_name = MagicMock()
        tracked_user_by_name.telegram_id = 555
        tracked_user_by_name.username = "suspect"

        tracked_user_full = MagicMock()
        tracked_user_full.telegram_id = 555
        tracked_user_full.username = "suspect"
        tracked_user_full.suspicion_score = 60.0
        tracked_user_full.added_at = datetime(2024, 1, 1)
        tracked_user_full.is_active = True
        tracked_user_full.notes = None
        tracked_user_full.id = 1

        # First call (username lookup) returns tracked_user_by_name
        # Second call (by telegram_id) returns tracked_user_full
        # Third, fourth, fifth calls for counts
        mock_result_name = MagicMock()
        mock_result_name.scalar_one_or_none.return_value = tracked_user_by_name

        mock_result_full = MagicMock()
        mock_result_full.scalar_one_or_none.return_value = tracked_user_full

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 5

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_result_name
            elif call_count[0] == 2:
                return mock_result_full
            else:
                return mock_result_count

        mock_session = AsyncMock()
        mock_session.execute = mock_execute

        async def mock_get_session():
            yield mock_session

        # Need to handle two separate "async for session in get_session()" calls
        # The first session yields for username resolution, the second for report data
        session_call_count = [0]

        async def mock_get_session_multi():
            session_call_count[0] += 1
            if session_call_count[0] == 1:
                mock_s = AsyncMock()
                r = MagicMock()
                r.scalar_one_or_none.return_value = tracked_user_by_name
                mock_s.execute = AsyncMock(return_value=r)
                yield mock_s
            else:
                mock_s = AsyncMock()
                exec_count = [0]

                async def exec_fn(q):
                    exec_count[0] += 1
                    if exec_count[0] == 1:
                        r = MagicMock()
                        r.scalar_one_or_none.return_value = tracked_user_full
                        return r
                    else:
                        r = MagicMock()
                        r.scalar.return_value = 5
                        return r

                mock_s.execute = exec_fn
                yield mock_s

        with patch("core.database.get_session", mock_get_session_multi):
            await cmd_report(update, context)

        # Should have called reply_text with report content
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "Report" in text or "suspect" in text

    @patch("bot.handler.get_settings")
    async def test_report_with_username_not_found(self, mock_settings):
        """cmd_report should reply not found when username is not tracked."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_report

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@nobody"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.get_session", mock_get_session):
            await cmd_report(update, context)

        update.message.reply_text.assert_called_once_with(
            "User nobody not found in tracking list."
        )

    @patch("bot.handler.get_settings")
    async def test_report_with_username_no_telegram_id(self, mock_settings):
        """cmd_report should reply no resolved ID when telegram_id is None."""
        mock_settings.return_value = MagicMock(my_telegram_id=123)

        from bot.handler import cmd_report

        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["@pending"]

        tracked_user = MagicMock()
        tracked_user.telegram_id = None
        tracked_user.username = "pending"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tracked_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.get_session", mock_get_session):
            await cmd_report(update, context)

        update.message.reply_text.assert_called_once_with(
            "User pending doesn't have a resolved Telegram ID yet."
        )
