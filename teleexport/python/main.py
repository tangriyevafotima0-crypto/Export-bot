#!/usr/bin/env python3
"""TeleExport Python Backend - JSON-RPC over stdin/stdout."""
import sys
import os
import asyncio
import signal

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.ipc.server import IPCServer
from python.ipc.handlers import register_handlers
from python.core.client import TeleExportClient
from python.core.config import setup_dirs


class App:
    """Main application class."""

    def __init__(self):
        self.server = IPCServer()
        self.client = TeleExportClient()
        self.current_export = None

    async def run(self):
        """Start the application."""
        setup_dirs()
        register_handlers(self.server, self)

        # Graceful shutdown
        loop = asyncio.get_event_loop()
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.shutdown)
        except NotImplementedError:
            # Windows does not support add_signal_handler
            pass

        await self.server.start()

    def shutdown(self):
        """Gracefully shutdown the application."""
        self.server._running = False
        if self.current_export:
            self.current_export.cancel()


if __name__ == "__main__":
    app = App()
    asyncio.run(app.run())
