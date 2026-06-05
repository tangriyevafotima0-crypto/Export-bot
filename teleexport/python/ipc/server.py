"""JSON-RPC server communicating over stdin/stdout with Electron."""
import sys
import json
import asyncio
import traceback
from typing import Callable, Dict, Any


class IPCServer:
    """stdin/stdout JSON-RPC server for Electron IPC."""

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()

    def register(self, method: str, handler: Callable):
        """Register an RPC method handler."""
        self.handlers[method] = handler

    async def start(self):
        """Start the server, reading from stdin and writing to stdout."""
        self._running = True
        loop = asyncio.get_event_loop()

        async def read_stdin():
            while self._running:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                line = line.strip()
                if line:
                    await self._handle_message(line)

        async def send_events():
            while self._running:
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(), timeout=0.5
                    )
                    sys.stdout.write(
                        json.dumps(event, ensure_ascii=False, default=str) + "\n"
                    )
                    sys.stdout.flush()
                except asyncio.TimeoutError:
                    continue

        await asyncio.gather(read_stdin(), send_events())

    async def _handle_message(self, raw: str):
        """Process an incoming JSON-RPC message."""
        try:
            msg = json.loads(raw)
            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            handler = self.handlers.get(method)
            if not handler:
                self._send_error(msg_id, -32601, f"Method not found: {method}")
                return

            # Call handler
            result = await handler(params, msg_id)

            # If handler returns a result, send it back
            if result is not None:
                self._send_result(msg_id, result)

        except json.JSONDecodeError:
            self._send_error(None, -32700, "Parse error")
        except Exception as e:
            self._send_error(
                msg.get("id") if "msg" in dir() else None, -32603, str(e)
            )
            traceback.print_exc(file=sys.stderr)

    def send_event(self, event_name: str, data: Any):
        """Queue an event to be sent to the client."""
        self._event_queue.put_nowait(
            {"id": None, "event": event_name, "data": data}
        )

    def _send_result(self, msg_id: str, result: Any):
        """Send a success response."""
        sys.stdout.write(
            json.dumps(
                {"id": msg_id, "result": result}, ensure_ascii=False, default=str
            )
            + "\n"
        )
        sys.stdout.flush()

    def _send_error(self, msg_id: str | None, code: int, message: str):
        """Send an error response."""
        sys.stdout.write(
            json.dumps(
                {"id": msg_id, "error": {"code": code, "message": message}},
                ensure_ascii=False,
            )
            + "\n"
        )
        sys.stdout.flush()
