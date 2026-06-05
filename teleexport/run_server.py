#!/usr/bin/env python3
"""TeleExport headless server runner.

Standalone script that runs the TeleExport Python backend without Electron.
Handles authentication interactively on first run, then runs as a daemon service
with a Unix socket JSON-RPC interface for triggering exports.
"""
import asyncio
import json
import os
import signal
import sys
import traceback
from pathlib import Path

# Ensure the teleexport directory is in the Python path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from python.core.config import setup_dirs, CONFIG_DIR, SESSION_DIR
from python.core.client import TeleExportClient
from python.core.auth import AuthManager


SOCKET_PATH = Path.home() / ".teleexport" / "teleexport.sock"


def load_config() -> dict:
    """Load API credentials from settings.json."""
    settings_file = CONFIG_DIR / "settings.json"
    if not settings_file.exists():
        print("\033[91mError: Config file not found at {}\033[0m".format(settings_file))
        print("Run deploy.sh first to configure credentials.")
        sys.exit(1)

    with open(settings_file, "r") as f:
        config = json.load(f)

    api_id = config.get("api_id")
    api_hash = config.get("api_hash")

    if not api_id or not api_hash:
        print("\033[91mError: api_id or api_hash missing from config.\033[0m")
        print("Run deploy.sh again to set credentials.")
        sys.exit(1)

    return {"api_id": int(api_id), "api_hash": str(api_hash)}


async def interactive_auth(client: TeleExportClient, auth: AuthManager, api_id: int, api_hash: str):
    """Handle interactive authentication flow with improved error handling."""
    print("\n\033[96m=== TeleExport Authentication ===\033[0m")
    print("No active session found. Starting authentication...\n")

    phone = input("\033[93mEnter your phone number (with country code, e.g. +1234567890): \033[0m").strip()
    if not phone:
        print("\033[91mError: Phone number cannot be empty.\033[0m")
        sys.exit(1)

    print("\033[96mSending verification code...\033[0m")
    try:
        result = await auth.send_code(phone, api_id, api_hash)
    except Exception as e:
        error_msg = str(e)
        if "FloodWait" in error_msg or "FLOOD" in error_msg:
            print("\033[91mError: Too many attempts. Telegram is rate-limiting you.\033[0m")
            print("\033[93mPlease wait a few minutes (or up to 24h) and try again.\033[0m")
        elif "PhoneNumberInvalid" in error_msg or "PHONE_NUMBER_INVALID" in error_msg:
            print("\033[91mError: Invalid phone number format.\033[0m")
            print("\033[93mMake sure to include the country code (e.g. +1 for US).\033[0m")
        elif "PhoneNumberBanned" in error_msg or "PHONE_NUMBER_BANNED" in error_msg:
            print("\033[91mError: This phone number has been banned by Telegram.\033[0m")
        elif "ApiIdInvalid" in error_msg or "API_ID_INVALID" in error_msg:
            print("\033[91mError: Invalid api_id or api_hash combination.\033[0m")
            print("\033[93mDouble-check your credentials at https://my.telegram.org\033[0m")
        else:
            print("\033[91mError sending code: {}\033[0m".format(error_msg))
        sys.exit(1)

    phone_code_hash = result["phone_code_hash"]

    code = input("\033[93mEnter the verification code you received: \033[0m").strip()
    if not code:
        print("\033[91mError: Verification code cannot be empty.\033[0m")
        sys.exit(1)

    try:
        sign_in_result = await auth.sign_in(phone, code, phone_code_hash)
    except Exception as e:
        error_msg = str(e)
        if "PhoneCodeExpired" in error_msg or "PHONE_CODE_EXPIRED" in error_msg:
            print("\033[91mError: Verification code has expired.\033[0m")
            print("\033[93mPlease re-run this script to request a new code.\033[0m")
        elif "PhoneCodeInvalid" in error_msg or "PHONE_CODE_INVALID" in error_msg:
            print("\033[91mError: Incorrect verification code.\033[0m")
            print("\033[93mPlease re-run this script and enter the correct code.\033[0m")
        elif "SessionPasswordNeeded" in error_msg or "Two" in error_msg:
            # 2FA needed -- handled below
            sign_in_result = {"success": False, "requires_2fa": True}
        else:
            print("\033[91mSign-in error: {}\033[0m".format(error_msg))
            print("\033[93mPlease re-run this script to try again.\033[0m")
            sys.exit(1)

    if not sign_in_result.get("success"):
        if sign_in_result.get("requires_2fa"):
            print("\033[93mTwo-factor authentication required.\033[0m")
            password = input("\033[93mEnter your 2FA password: \033[0m").strip()
            if not password:
                print("\033[91mError: 2FA password cannot be empty.\033[0m")
                sys.exit(1)
            try:
                sign_in_result = await auth.sign_in_2fa(password)
            except Exception as e:
                error_msg = str(e)
                if "PasswordHashInvalid" in error_msg or "PASSWORD_HASH_INVALID" in error_msg:
                    print("\033[91mError: Incorrect 2FA password.\033[0m")
                    print("\033[93mPlease re-run this script and enter the correct password.\033[0m")
                else:
                    print("\033[91m2FA error: {}\033[0m".format(error_msg))
                sys.exit(1)
        else:
            print("\033[91mError: Sign-in failed.\033[0m")
            sys.exit(1)

    if sign_in_result.get("success"):
        user = sign_in_result["user"]
        print("\n\033[92mAuthenticated successfully!\033[0m")
        print("  User: {} {}".format(
            user.get("first_name", ""),
            user.get("last_name", "") or ""
        ).strip())
        if user.get("username"):
            print("  Username: @{}".format(user["username"]))
        print("")
    else:
        print("\033[91mAuthentication failed.\033[0m")
        sys.exit(1)


class UnixSocketRPCServer:
    """JSON-RPC server over a Unix domain socket for triggering exports."""

    def __init__(self, client: TeleExportClient, socket_path: Path):
        self.client = client
        self.socket_path = socket_path
        self.handlers = {}
        self._server = None
        self._register_handlers()

    def _register_handlers(self):
        """Register available RPC methods."""
        self.handlers["export.start"] = self._handle_export_start
        self.handlers["export.status"] = self._handle_export_status
        self.handlers["chats.list"] = self._handle_chats_list
        self.handlers["ping"] = self._handle_ping

    async def _handle_ping(self, params: dict) -> dict:
        """Health check."""
        return {"status": "ok", "service": "teleexport"}

    async def _handle_chats_list(self, params: dict) -> dict:
        """List available chats."""
        from python.export.chat_scanner import ChatScanner
        scanner = ChatScanner(self.client.client)
        limit = params.get("limit", 100)
        chats = await scanner.scan_all(limit=limit)
        return {"chats": chats, "total": len(chats)}

    async def _handle_export_start(self, params: dict) -> dict:
        """Start an export operation."""
        from python.export.engine import ExportEngine, ExportConfig
        from python.core.config import EXPORTS_DIR
        import uuid
        from datetime import datetime, timezone

        chat_ids = params.get("chat_ids")
        if not chat_ids:
            return {"error": "chat_ids is required"}

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

        media_types = set(params.get("media_types", [
            "photo", "video", "audio", "document", "voice", "sticker"
        ]))

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

        export_id = "exp_{}".format(uuid.uuid4().hex[:8])

        def progress_callback(event_name, data):
            # In daemon mode we log progress to journal
            print("[export:{}] {}: {}".format(export_id, event_name, json.dumps(data, default=str)))

        engine = ExportEngine(self.client, config, progress_callback)

        async def run_export():
            try:
                stats = await engine.run(export_id)
                print("[export:{}] complete: {}".format(export_id, json.dumps(stats, default=str)))
            except Exception as e:
                print("[export:{}] error: {}".format(export_id, str(e)))

        asyncio.create_task(run_export())
        return {"export_id": export_id, "status": "started"}

    async def _handle_export_status(self, params: dict) -> dict:
        """Get export status (placeholder for future tracking)."""
        return {"status": "idle"}

    async def start(self):
        """Start the Unix socket server."""
        # Remove stale socket file
        if self.socket_path.exists():
            self.socket_path.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=str(self.socket_path)
        )

        # Set socket permissions so only the owning user can connect
        os.chmod(self.socket_path, 0o700)

        print("\033[92m[TeleExport] Unix socket server listening at: {}\033[0m".format(self.socket_path))

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single client connection."""
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                line = data.decode("utf-8").strip()
                if not line:
                    continue
                response = await self._process_message(line)
                writer.write((json.dumps(response, default=str) + "\n").encode("utf-8"))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print("[TeleExport] Socket handler error: {}".format(e))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_message(self, raw: str) -> dict:
        """Process a JSON-RPC message and return the response."""
        msg_id = None
        try:
            msg = json.loads(raw)
            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            handler = self.handlers.get(method)
            if not handler:
                return {"id": msg_id, "error": {"code": -32601, "message": "Method not found: {}".format(method)}}

            result = await handler(params)
            return {"id": msg_id, "result": result}
        except json.JSONDecodeError:
            return {"id": None, "error": {"code": -32700, "message": "Parse error"}}
        except Exception as e:
            traceback.print_exc()
            return {"id": msg_id, "error": {"code": -32603, "message": str(e)}}

    async def stop(self):
        """Stop the socket server and clean up."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self.socket_path.exists():
            self.socket_path.unlink()


async def run_daemon(client: TeleExportClient):
    """Run as a daemon with Unix socket RPC interface."""
    print("\033[92m[TeleExport] Service running. Client connected and ready.\033[0m")
    print("[TeleExport] Press Ctrl+C to stop (or send SIGTERM).")

    # Start Unix socket JSON-RPC server
    rpc_server = UnixSocketRPCServer(client, SOCKET_PATH)
    await rpc_server.start()

    stop_event = asyncio.Event()

    def handle_signal():
        print("\n\033[93m[TeleExport] Shutdown signal received...\033[0m")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    # Keep alive until signaled to stop
    await stop_event.wait()

    print("\033[96m[TeleExport] Stopping socket server...\033[0m")
    await rpc_server.stop()
    print("\033[96m[TeleExport] Disconnecting client...\033[0m")
    await client.disconnect()
    print("\033[92m[TeleExport] Shutdown complete.\033[0m")


async def main():
    """Main entry point for headless TeleExport server."""
    # Setup directories
    setup_dirs()

    # Load config
    config = load_config()
    api_id = config["api_id"]
    api_hash = config["api_hash"]

    # Initialize client
    client = TeleExportClient(session_name="server")
    await client.init(api_id, api_hash)

    # Check if already authorized
    is_authorized = await client.connect()

    if not is_authorized:
        # Need interactive auth
        if not sys.stdin.isatty():
            print("\033[91mError: No active session and stdin is not a terminal.\033[0m")
            print("Run this script manually first to complete authentication:")
            print("  python3 {}".format(Path(__file__).resolve()))
            await client.disconnect()
            sys.exit(1)

        auth = AuthManager(client)
        await interactive_auth(client, auth, api_id, api_hash)
    else:
        me = await client.get_me()
        print("\033[92m[TeleExport] Session active for: {} {}\033[0m".format(
            me.first_name or "",
            me.last_name or ""
        ).strip())

    # Run as daemon
    await run_daemon(client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\033[93m[TeleExport] Interrupted.\033[0m")
    except Exception as e:
        print("\033[91m[TeleExport] Fatal error: {}\033[0m".format(e))
        traceback.print_exc()
        sys.exit(1)
