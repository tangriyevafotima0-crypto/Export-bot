"""Tests for the IPC JSON-RPC server."""
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO

import pytest

from python.ipc.server import IPCServer


class TestIPCServer:
    """Tests for IPCServer handler registration and message processing."""

    def test_register_handler(self):
        """Test handler registration stores the handler."""
        server = IPCServer()
        handler = AsyncMock()
        server.register("test_method", handler)
        assert "test_method" in server.handlers
        assert server.handlers["test_method"] is handler

    def test_register_multiple_handlers(self):
        """Test registering multiple handlers."""
        server = IPCServer()
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        server.register("method_a", handler1)
        server.register("method_b", handler2)
        assert len(server.handlers) == 2
        assert server.handlers["method_a"] is handler1
        assert server.handlers["method_b"] is handler2

    @pytest.mark.asyncio
    async def test_handle_message_dispatches_to_handler(self):
        """Test that _handle_message dispatches to the correct handler."""
        server = IPCServer()
        handler = AsyncMock(return_value={"status": "ok"})
        server.register("do_something", handler)

        request = json.dumps({
            "id": "req-1",
            "method": "do_something",
            "params": {"key": "value"},
        })

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            await server._handle_message(request)

        handler.assert_awaited_once_with({"key": "value"}, "req-1")

    @pytest.mark.asyncio
    async def test_handle_message_sends_result(self):
        """Test that handler result is sent as JSON-RPC response."""
        server = IPCServer()
        handler = AsyncMock(return_value={"data": 42})
        server.register("get_data", handler)

        request = json.dumps({
            "id": "req-2",
            "method": "get_data",
            "params": {},
        })

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            await server._handle_message(request)

        output = mock_stdout.getvalue().strip()
        response = json.loads(output)
        assert response["id"] == "req-2"
        assert response["result"] == {"data": 42}

    @pytest.mark.asyncio
    async def test_handle_message_unknown_method(self):
        """Test that unknown method returns error response."""
        server = IPCServer()

        request = json.dumps({
            "id": "req-3",
            "method": "nonexistent_method",
            "params": {},
        })

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            await server._handle_message(request)

        output = mock_stdout.getvalue().strip()
        response = json.loads(output)
        assert response["id"] == "req-3"
        assert response["error"]["code"] == -32601
        assert "nonexistent_method" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_handle_message_malformed_json(self):
        """Test that malformed JSON returns parse error."""
        server = IPCServer()

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            await server._handle_message("this is not json {{{")

        output = mock_stdout.getvalue().strip()
        response = json.loads(output)
        assert response["id"] is None
        assert response["error"]["code"] == -32700
        assert "Parse error" in response["error"]["message"]

    def test_send_event_format(self):
        """Test that send_event queues events in the correct format."""
        server = IPCServer()
        server.send_event("progress", {"percent": 50})

        event = server._event_queue.get_nowait()
        assert event["id"] is None
        assert event["event"] == "progress"
        assert event["data"] == {"percent": 50}

    def test_send_event_multiple(self):
        """Test sending multiple events queues them in order."""
        server = IPCServer()
        server.send_event("start", {"task": "export"})
        server.send_event("progress", {"percent": 25})
        server.send_event("done", {"result": "success"})

        assert server._event_queue.qsize() == 3
        e1 = server._event_queue.get_nowait()
        e2 = server._event_queue.get_nowait()
        e3 = server._event_queue.get_nowait()
        assert e1["event"] == "start"
        assert e2["event"] == "progress"
        assert e3["event"] == "done"

    @pytest.mark.asyncio
    async def test_handle_message_default_params(self):
        """Test that missing params defaults to empty dict."""
        server = IPCServer()
        handler = AsyncMock(return_value=None)
        server.register("no_params", handler)

        request = json.dumps({"id": "req-4", "method": "no_params"})

        with patch("sys.stdout", new_callable=StringIO):
            await server._handle_message(request)

        handler.assert_awaited_once_with({}, "req-4")
