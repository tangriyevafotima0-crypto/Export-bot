"""Register all RPC method handlers for the IPC server."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .server import IPCServer
from ..core.auth import AuthManager
from ..core.session_manager import SessionManager
from ..core.config import DEFAULT_SETTINGS, EXPORTS_DIR, CONFIG_DIR
from ..export.engine import ExportEngine, ExportConfig
from ..export.chat_scanner import ChatScanner

SETTINGS_FILE = CONFIG_DIR / "settings.json"


def _load_settings() -> dict:
    """Load settings from disk, falling back to defaults."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            settings.update(saved)
    except (json.JSONDecodeError, OSError):
        pass
    return settings


def _save_settings(settings: dict) -> tuple[bool, str | None]:
    """Persist settings to disk. Returns (success, error_message)."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2, default=str)
        return (True, None)
    except OSError as e:
        return (False, str(e))


def register_handlers(server: IPCServer, app):
    """Register all RPC methods on the server."""

    auth_manager = AuthManager(app.client)
    session_manager = SessionManager()
    _settings = _load_settings()

    # Dict of active exports keyed by export_id
    if not hasattr(app, "exports"):
        app.exports = {}

    # ============ AUTH ============

    async def auth_check_session(params, msg_id):
        # On cold start, client is None. If we have persisted api credentials,
        # initialize the client so check_session can verify the session file.
        if app.client.client is None:
            api_id = _settings.get("api_id")
            api_hash = _settings.get("api_hash")
            if api_id and api_hash:
                await app.client.init(int(api_id), str(api_hash))
        return await auth_manager.check_session()

    async def auth_send_code(params, msg_id):
        phone = params["phone"]
        api_id = params["api_id"]
        api_hash = params["api_hash"]
        result = await auth_manager.send_code(phone, api_id, api_hash)
        # Persist api_id and api_hash for session resume on future cold starts
        _settings["api_id"] = api_id
        _settings["api_hash"] = api_hash
        _save_settings(_settings)
        server.send_event("auth.code_sent", {"phone": phone})
        return result

    async def auth_sign_in(params, msg_id):
        phone = params["phone"]
        code = params["code"]
        phone_code_hash = params["phone_code_hash"]
        result = await auth_manager.sign_in(phone, code, phone_code_hash)
        if result.get("success"):
            server.send_event("auth.signed_in", result.get("user"))
        return result

    async def auth_check_2fa(params, msg_id):
        return await auth_manager.check_2fa()

    async def auth_sign_in_2fa(params, msg_id):
        password = params["password"]
        return await auth_manager.sign_in_2fa(password)

    async def auth_resend_code(params, msg_id):
        phone = params["phone"]
        api_id = params.get("api_id") or _settings.get("api_id")
        api_hash = params.get("api_hash") or _settings.get("api_hash")
        if not api_id or not api_hash:
            return {"error": "api_id and api_hash required"}
        result = await auth_manager.resend_code(phone, int(api_id), str(api_hash))
        server.send_event("auth.code_resent", {"phone": phone, "code_type": result.get("code_type")})
        return result

    async def auth_logout(params, msg_id):
        return await auth_manager.logout()

    # ============ CHATS ============

    async def chats_list(params, msg_id):
        scanner = ChatScanner(app.client.client)
        limit = params.get("limit", 100)
        offset = params.get("offset", 0)
        search = params.get("search")
        # Scan a reasonable max number of dialogs, independent of pagination
        scan_limit = 500
        chats = await scanner.scan_all(limit=scan_limit)

        if search:
            search_lower = search.lower()
            chats = [
                c for c in chats if search_lower in c["name"].lower()
            ]

        total = len(chats)
        chats = chats[offset : offset + limit]
        return {"chats": chats, "total": total}

    async def chats_get_details(params, msg_id):
        chat_id = params["chat_id"]
        entity = await app.client.client.get_entity(chat_id)
        return {
            "chat": {
                "id": entity.id,
                "name": getattr(entity, "title", None)
                or f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip(),
                "type": _get_entity_type(entity),
            }
        }

    # ============ EXPORT ============

    async def export_start(params, msg_id):
        export_id = f"exp_{uuid.uuid4().hex[:8]}"
        chat_ids = params["chat_ids"]
        fmt = params.get("format", "html")
        output_dir = Path(params.get("output_dir", str(EXPORTS_DIR)))

        date_from = None
        date_to = None
        if params.get("date_from"):
            date_from = datetime.fromisoformat(params["date_from"])
            if date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
        if params.get("date_to"):
            date_to = datetime.fromisoformat(params["date_to"])
            if date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)

        media_types = set(
            params.get("media_types", DEFAULT_SETTINGS["media_types"])
        )

        config = ExportConfig(
            chat_ids=chat_ids,
            output_dir=output_dir,
            format=fmt,
            date_from=date_from,
            date_to=date_to,
            media_types=media_types,
            include_replies=params.get("include_replies", True),
            include_forwards=params.get("include_forwards", True),
            max_file_size_mb=params.get("max_file_size_mb", 500),
        )

        def progress_callback(event_name, data):
            server.send_event(event_name, data)

        engine = ExportEngine(app.client, config, progress_callback)

        # Run export in background
        import asyncio

        async def run_export():
            try:
                stats = await engine.run(export_id)
                server.send_event(
                    "export.complete",
                    {
                        "export_id": export_id,
                        "total_chats": stats["total_chats"],
                        "total_messages": stats["total_messages"],
                        "total_media": stats["total_media"],
                        "output_path": str(output_dir),
                    },
                )
            except Exception as e:
                server.send_event(
                    "export.error",
                    {
                        "export_id": export_id,
                        "error_message": str(e),
                        "recoverable": False,
                    },
                )
            finally:
                app.exports.pop(export_id, None)

        task = asyncio.create_task(run_export())
        app.exports[export_id] = (engine, task)
        return {"export_id": export_id}

    async def export_cancel(params, msg_id):
        export_id = params.get("export_id")
        entry = app.exports.get(export_id)
        if entry:
            engine, task = entry
            engine.cancel()
            return {"success": True}
        return {"success": False}

    async def export_get_status(params, msg_id):
        export_id = params.get("export_id")
        if export_id and export_id in app.exports:
            return {"status": "running", "export_id": export_id}
        if app.exports:
            return {"status": "running", "active_exports": list(app.exports.keys())}
        return {"status": "idle"}

    # ============ SETTINGS ============

    async def settings_get(params, msg_id):
        return {"settings": _settings}

    async def settings_set(params, msg_id):
        new_settings = params.get("settings", {})
        _settings.update(new_settings)
        ok, err = _save_settings(_settings)
        if not ok:
            return {"success": False, "error": err}
        return {"success": True}

    # Register all handlers
    server.register("auth.check_session", auth_check_session)
    server.register("auth.send_code", auth_send_code)
    server.register("auth.resend_code", auth_resend_code)
    server.register("auth.sign_in", auth_sign_in)
    server.register("auth.check_2fa", auth_check_2fa)
    server.register("auth.sign_in_2fa", auth_sign_in_2fa)
    server.register("auth.logout", auth_logout)
    server.register("chats.list", chats_list)
    server.register("chats.get_details", chats_get_details)
    server.register("export.start", export_start)
    server.register("export.cancel", export_cancel)
    server.register("export.get_status", export_get_status)
    server.register("settings.get", settings_get)
    server.register("settings.set", settings_set)


def _get_entity_type(entity) -> str:
    """Determine entity type."""
    if hasattr(entity, "broadcast") and entity.broadcast:
        return "channel"
    if hasattr(entity, "megagroup") and entity.megagroup:
        return "group"
    return "private"
