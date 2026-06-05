"""Tests for the MessageFetcher."""
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

import pytest

from python.export.message_fetcher import MessageFetcher


class TestMessageFetcherInit:
    """Tests for MessageFetcher initialization."""

    def test_default_batch_size(self, mock_telegram_client, mock_entity):
        """Test default batch_size is 100."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity)
        assert fetcher.batch_size == 100

    def test_custom_batch_size(self, mock_telegram_client, mock_entity):
        """Test custom batch_size configuration."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity, batch_size=50)
        assert fetcher.batch_size == 50

    def test_date_filters(self, mock_telegram_client, mock_entity):
        """Test initialization with date filters."""
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 6, 30)
        fetcher = MessageFetcher(
            mock_telegram_client, mock_entity,
            date_from=date_from,
            date_to=date_to,
        )
        assert fetcher.date_from == date_from
        assert fetcher.date_to == date_to

    def test_no_date_filters(self, mock_telegram_client, mock_entity):
        """Test initialization without date filters."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity)
        assert fetcher.date_from is None
        assert fetcher.date_to is None

    def test_initial_processed_is_zero(self, mock_telegram_client, mock_entity):
        """Test that processed counter starts at zero."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity)
        assert fetcher.processed == 0

    def test_initial_total_is_none(self, mock_telegram_client, mock_entity):
        """Test that total starts as None."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity)
        assert fetcher.total is None

    def test_stores_entity(self, mock_telegram_client, mock_entity):
        """Test that entity is stored."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity)
        assert fetcher.entity is mock_entity

    def test_stores_client(self, mock_telegram_client, mock_entity):
        """Test that client is stored."""
        fetcher = MessageFetcher(mock_telegram_client, mock_entity)
        assert fetcher.client is mock_telegram_client
