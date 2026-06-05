"""IPC message types and serialization helpers."""
from dataclasses import dataclass, field
from typing import Any, Optional
import json


@dataclass
class IPCMessage:
    """Represents an IPC message (request, response, or event)."""

    id: Optional[str] = None
    method: Optional[str] = None
    params: dict = field(default_factory=dict)
    result: Any = None
    error: Optional[dict] = None
    event: Optional[str] = None
    data: Any = None

    @classmethod
    def from_json(cls, raw: str) -> "IPCMessage":
        """Parse a JSON string into an IPCMessage."""
        obj = json.loads(raw)
        return cls(
            id=obj.get("id"),
            method=obj.get("method"),
            params=obj.get("params", {}),
            result=obj.get("result"),
            error=obj.get("error"),
            event=obj.get("event"),
            data=obj.get("data"),
        )

    def to_json(self) -> str:
        """Serialize the message to JSON string."""
        obj = {}
        if self.id is not None:
            obj["id"] = self.id
        if self.method is not None:
            obj["method"] = self.method
        if self.params:
            obj["params"] = self.params
        if self.result is not None:
            obj["result"] = self.result
        if self.error is not None:
            obj["error"] = self.error
        if self.event is not None:
            obj["event"] = self.event
        if self.data is not None:
            obj["data"] = self.data
        return json.dumps(obj, ensure_ascii=False, default=str)

    @staticmethod
    def request(msg_id: str, method: str, params: dict = None) -> "IPCMessage":
        """Create a request message."""
        return IPCMessage(id=msg_id, method=method, params=params or {})

    @staticmethod
    def response(msg_id: str, result: Any) -> "IPCMessage":
        """Create a success response."""
        return IPCMessage(id=msg_id, result=result)

    @staticmethod
    def error_response(msg_id: Optional[str], code: int, message: str) -> "IPCMessage":
        """Create an error response."""
        return IPCMessage(id=msg_id, error={"code": code, "message": message})

    @staticmethod
    def event_message(event_name: str, data: Any) -> "IPCMessage":
        """Create an event message (no id)."""
        return IPCMessage(id=None, event=event_name, data=data)
