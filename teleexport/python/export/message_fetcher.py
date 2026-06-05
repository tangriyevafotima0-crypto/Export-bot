"""Message fetcher for efficient batch retrieval from Telegram."""
import asyncio
from typing import AsyncIterator, Optional
from datetime import datetime

from telethon import TelegramClient


class MessageFetcher:
    """Fetches messages in efficient batches.

    Uses takeout session for faster export with reduced flood wait.
    Falls back to standard iter_messages if takeout is unavailable.
    """

    def __init__(
        self,
        client: TelegramClient,
        entity,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        batch_size: int = 100,
    ):
        self.client = client
        self.entity = entity
        self.date_from = date_from
        self.date_to = date_to
        self.batch_size = batch_size
        self.processed = 0
        self.total: Optional[int] = None

    async def count_total(self) -> int:
        """Count total messages in the date range."""
        if self.total is None:
            count = 0
            async for msg in self.client.iter_messages(
                self.entity,
                offset_date=self.date_to,
                offset_id=0,
                limit=None,
            ):
                if self.date_from and msg.date.replace(tzinfo=None) < self.date_from:
                    break
                count += 1
            self.total = count
        return self.total

    async def iter_batches(self) -> AsyncIterator[list]:
        """Iterate over messages in batches, using takeout session with fallback."""
        try:
            async with self.client.takeout() as takeout:
                messages = []
                async for msg in takeout.iter_messages(
                    self.entity,
                    offset_date=self.date_to,
                    limit=None,
                    wait_time=0,
                ):
                    if self.date_from and msg.date.replace(tzinfo=None) < self.date_from:
                        if messages:
                            yield messages
                        break

                    messages.append(msg)
                    self.processed += 1

                    if len(messages) >= self.batch_size:
                        yield messages
                        messages = []
                        await asyncio.sleep(0.05)

                if messages:
                    yield messages

        except Exception:
            # Takeout unavailable, fallback to standard iteration
            async for batch in self._iter_without_takeout():
                yield batch

    async def _iter_without_takeout(self) -> AsyncIterator[list]:
        """Standard message iteration without takeout session."""
        per_chat_delay = 1.0
        if hasattr(self.entity, "broadcast") and self.entity.broadcast:
            per_chat_delay = 3.0

        messages = []
        async for msg in self.client.iter_messages(
            self.entity,
            offset_date=self.date_to,
            limit=None,
        ):
            if self.date_from and msg.date.replace(tzinfo=None) < self.date_from:
                if messages:
                    yield messages
                break

            messages.append(msg)
            self.processed += 1

            if len(messages) >= self.batch_size:
                yield messages
                messages = []
                await asyncio.sleep(per_chat_delay)

        if messages:
            yield messages
