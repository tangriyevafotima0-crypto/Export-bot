#!/usr/bin/env python3
"""TeleExport headless server runner.

Standalone script that runs the TeleExport Python backend without Electron.
Handles authentication interactively on first run, then runs as a daemon service
with a Unix socket JSON-RPC interface for triggering exports.

IMPORTANT: This script fixes the auth code delivery issue by:
1. Cleaning session files BEFORE creating the client (not after)
2. Using correct session path (without .session extension - Telethon adds it)
3. Single initialization path - no double init/connect
4. Using raw ResendCodeRequest API for SMS (force_sms is deprecated and broken)
5. Both app and SMS delivery are attempted - code is sent to BOTH methods
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


def clean_session_files():
    """Remove stale session files from ~/.teleexport/sessions/ for a clean auth start.

    This prevents conflicts from previously used api_id with different phone/account.
    Must be called BEFORE creating/connecting a TelegramClient.
    """
    if not SESSION_DIR.exists():
        return

    # Telethon creates files like "server.session" (it adds .session to the name we give)
    session_files = list(SESSION_DIR.glob("*.session"))
    journal_files = list(SESSION_DIR.glob("*.session-journal"))

    all_files = session_files + journal_files
    if all_files:
        print("\033[93m[Session Cleanup] Found {} session file(s):\033[0m".format(len(all_files)))
        for sf in all_files:
            print("  Removing: {}".format(sf.name))
            sf.unlink()
        print("\033[92m[Session Cleanup] Done. Starting with clean session.\033[0m\n")
    else:
        print("\033[96m[Session] No stale sessions found. Clean start.\033[0m\n")


async def interactive_auth(api_id: int, api_hash: str):
    """Handle interactive authentication flow.

    This creates a fresh client after cleaning sessions, performs authentication,
    and returns the connected+authenticated client.

    Auth code delivery strategy:
    1. First send_code -> code goes to Telegram app (SentCodeTypeApp)
    2. Immediately offer to resend via SMS using raw ResendCodeRequest API
    3. If still not received, offer another resend (may trigger phone call)
    """
    print("\n\033[96m=== TeleExport Authentication ===\033[0m")
    print("No active session found. Starting authentication...\n")

    # Step 1: Clean session files BEFORE creating client
    clean_session_files()

    # Step 2: Create fresh client and connect (single init path)
    client = TeleExportClient(session_name="server")
    await client.init(api_id, api_hash)
    await client.connect()

    print("\033[92m[DEBUG] Client initialized and connected.\033[0m")
    print("\033[96m[DEBUG] Session path: {}\033[0m".format(client.session_path))

    # Step 3: Create auth manager with this client
    auth = AuthManager(client)

    # Step 4: Get phone number
    phone = input("\033[93mTelefon raqamingizni kiriting (masalan +998901234567): \033[0m").strip()
    if not phone:
        print("\033[91mXato: Telefon raqami bo'sh bo'lishi mumkin emas.\033[0m")
        await client.disconnect()
        sys.exit(1)

    # Step 5: Send verification code (first call - goes to Telegram app)
    print("\033[96mVerifikatsiya kodi yuborilmoqda {}...\033[0m".format(phone))
    try:
        result = await auth.send_code(phone, api_id, api_hash)
    except Exception as e:
        error_msg = str(e)
        if "FloodWait" in error_msg or "FLOOD" in error_msg:
            print("\033[91mXato: Juda ko'p urinish. Telegram cheklov qo'ydi.\033[0m")
            print("\033[93mBir necha daqiqa (yoki 24 soatgacha) kuting va qayta urinib ko'ring.\033[0m")
        elif "PhoneNumberInvalid" in error_msg or "PHONE_NUMBER_INVALID" in error_msg:
            print("\033[91mXato: Telefon raqami formati noto'g'ri.\033[0m")
            print("\033[93mDavlat kodini kiritganingizga ishonch hosil qiling (masalan +998).\033[0m")
        elif "PhoneNumberBanned" in error_msg or "PHONE_NUMBER_BANNED" in error_msg:
            print("\033[91mXato: Bu telefon raqami Telegram tomonidan bloklangan.\033[0m")
        elif "ApiIdInvalid" in error_msg or "API_ID_INVALID" in error_msg:
            print("\033[91mXato: api_id yoki api_hash noto'g'ri.\033[0m")
            print("\033[93mhttps://my.telegram.org da tekshiring.\033[0m")
        else:
            print("\033[91mKod yuborishda xato: {}\033[0m".format(error_msg))
            traceback.print_exc()
        await client.disconnect()
        sys.exit(1)

    phone_code_hash = result["phone_code_hash"]

    # Show debug info about how code was delivered
    code_type = result.get("code_type", "Unknown")
    timeout = result.get("timeout", 60)
    print("\033[92m[OK] Kod yuborildi!\033[0m")
    print("\033[96m[DEBUG] Yetkazish usuli: {}\033[0m".format(code_type))
    print("\033[96m[DEBUG] Kod muddati: {} soniya\033[0m".format(timeout))
    print("\033[96m[DEBUG] Phone code hash: {}...\033[0m".format(phone_code_hash[:8]))
    print("")

    # Step 6: Immediately offer SMS resend since app delivery often fails
    print("\033[93mKod ilovaga yuborildi. Agar kelmasa, SMS orqali yuboramizmi?\033[0m")
    print("\033[93m[y/Enter] = SMS orqali qayta yuborish | [kodni kiriting] = davom etish\033[0m")
    print("")

    code = input("\033[93mKodni kiriting yoki SMS uchun Enter bosing: \033[0m").strip()

    # If user pressed Enter or typed 'y' - resend via SMS using raw API
    if not code or code.lower() in ("y", "yes", "ha", "sms"):
        print("\n\033[96mSMS orqali qayta yuborilmoqda (ResendCodeRequest)...\033[0m")
        try:
            result = await auth.resend_code(phone, api_id, api_hash)
            phone_code_hash = result["phone_code_hash"]
            code_type = result.get("code_type", "Unknown")
            print("\033[92m[OK] Kod SMS orqali qayta yuborildi!\033[0m")
            print("\033[96m[DEBUG] Yangi yetkazish usuli: {}\033[0m".format(code_type))
            print("\033[93mSMS xabarlarni tekshiring.\033[0m")
            print("")
        except Exception as e:
            error_msg = str(e)
            if "FloodWait" in error_msg or "FLOOD" in error_msg:
                print("\033[91mXato: Juda ko'p urinish. Kuting va qayta urinib ko'ring.\033[0m")
                await client.disconnect()
                sys.exit(1)
            else:
                print("\033[91mQayta yuborishda xato: {}\033[0m".format(error_msg))
                print("\033[93mSkriptni qaytadan ishga tushirib ko'ring.\033[0m")
                await client.disconnect()
                sys.exit(1)

        code = input("\033[93mSMS dan kelgan kodni kiriting (yoki qo'ng'iroq uchun Enter): \033[0m").strip()

        # If still no code, try one more resend (may trigger phone call)
        if not code or code.lower() in ("y", "yes", "ha", "call"):
            print("\n\033[96mQo'ng'iroq orqali yuborilmoqda (ikkinchi ResendCodeRequest)...\033[0m")
            try:
                result = await auth.resend_code(phone, api_id, api_hash)
                phone_code_hash = result["phone_code_hash"]
                code_type = result.get("code_type", "Unknown")
                print("\033[92m[OK] Kod qayta yuborildi!\033[0m")
                print("\033[96m[DEBUG] Yetkazish usuli: {}\033[0m".format(code_type))
                if "Call" in code_type:
                    print("\033[93mTelegram qo'ng'iroq qiladi, kodni eshiting.\033[0m")
                else:
                    print("\033[93mKodni tekshiring ({}).\033[0m".format(code_type))
                print("")
            except Exception as e:
                error_msg = str(e)
                if "FloodWait" in error_msg or "FLOOD" in error_msg:
                    print("\033[91mXato: Juda ko'p urinish. Kuting.\033[0m")
                    await client.disconnect()
                    sys.exit(1)
                else:
                    print("\033[91mQayta yuborishda xato: {}\033[0m".format(error_msg))
                    print("\033[93mSkriptni qaytadan ishga tushiring.\033[0m")
                    await client.disconnect()
                    sys.exit(1)

            code = input("\033[93mKodni kiriting: \033[0m").strip()
            if not code:
                print("\033[91mXato: Verifikatsiya kodi bo'sh bo'lishi mumkin emas.\033[0m")
                await client.disconnect()
                sys.exit(1)

    # Step 7: Sign in with the code.
    # Retry on an invalid code (same phone_code_hash) and auto-resend on an
    # expired code, so a single typo no longer forces a full restart (which
    # would request a brand new code and push the account toward a flood-wait).
    sign_in_result = None
    max_attempts = 3
    attempt = 0
    while sign_in_result is None:
        attempt += 1
        print("\033[96mTizimga kirilmoqda...\033[0m")
        try:
            sign_in_result = await auth.sign_in(phone, code, phone_code_hash)
        except Exception as e:
            error_msg = str(e)
            if "PhoneCodeInvalid" in error_msg or "PHONE_CODE_INVALID" in error_msg:
                print("\033[91mXato: Verifikatsiya kodi noto'g'ri.\033[0m")
                if attempt >= max_attempts:
                    print("\033[91mJuda ko'p noto'g'ri urinish. Skriptni qayta ishga tushiring.\033[0m")
                    await client.disconnect()
                    sys.exit(1)
                code = input("\033[93mKodni qayta kiriting: \033[0m").strip()
                if not code:
                    print("\033[91mXato: Kod bo'sh bo'lishi mumkin emas.\033[0m")
                    await client.disconnect()
                    sys.exit(1)
                continue
            elif "PhoneCodeExpired" in error_msg or "PHONE_CODE_EXPIRED" in error_msg:
                print("\033[91mXato: Verifikatsiya kodi muddati tugagan.\033[0m")
                print("\033[96mYangi kod SMS orqali yuborilmoqda...\033[0m")
                try:
                    resend = await auth.resend_code(phone, api_id, api_hash)
                    phone_code_hash = resend["phone_code_hash"]
                    print("\033[92m[OK] Yangi kod yuborildi ({}).\033[0m".format(
                        resend.get("code_type", "Unknown")))
                except Exception as re_err:
                    print("\033[91mYangi kod yuborishda xato: {}\033[0m".format(re_err))
                    print("\033[93mSkriptni qayta ishga tushiring.\033[0m")
                    await client.disconnect()
                    sys.exit(1)
                code = input("\033[93mYangi kodni kiriting: \033[0m").strip()
                if not code:
                    print("\033[91mXato: Kod bo'sh bo'lishi mumkin emas.\033[0m")
                    await client.disconnect()
                    sys.exit(1)
                continue
            elif (
                "SessionPasswordNeeded" in error_msg
                or "two-step" in error_msg.lower()
                or "password is required" in error_msg.lower()
            ):
                # 2FA needed - handle below
                sign_in_result = {"success": False, "requires_2fa": True}
            else:
                print("\033[91mTizimga kirishda xato: {}\033[0m".format(error_msg))
                print("\033[93mSkriptni qayta ishga tushiring.\033[0m")
                await client.disconnect()
                sys.exit(1)

    # Step 8: Handle 2FA if needed
    if not sign_in_result.get("success"):
        if sign_in_result.get("requires_2fa"):
            print("\033[93mIkki bosqichli autentifikatsiya kerak.\033[0m")
            password = input("\033[93m2FA parolni kiriting: \033[0m").strip()
            if not password:
                print("\033[91mXato: 2FA parol bo'sh bo'lishi mumkin emas.\033[0m")
                await client.disconnect()
                sys.exit(1)
            try:
                sign_in_result = await auth.sign_in_2fa(password)
            except Exception as e:
                error_msg = str(e)
                if "PasswordHashInvalid" in error_msg or "PASSWORD_HASH_INVALID" in error_msg:
                    print("\033[91mXato: 2FA parol noto'g'ri.\033[0m")
                    print("\033[93mSkriptni qayta ishga tushiring.\033[0m")
                else:
                    print("\033[91m2FA xato: {}\033[0m".format(error_msg))
                await client.disconnect()
                sys.exit(1)
        else:
            print("\033[91mXato: Tizimga kirish muvaffaqiyatsiz.\033[0m")
            await client.disconnect()
            sys.exit(1)

    # Step 9: Verify success
    if sign_in_result.get("success"):
        user = sign_in_result["user"]
        print("\n\033[92mMuvaffaqiyatli autentifikatsiya!\033[0m")
        print("  Foydalanuvchi: {} {}".format(
            user.get("first_name", ""),
            user.get("last_name", "") or ""
        ).strip())
        if user.get("username"):
            print("  Username: @{}".format(user["username"]))
        print("")
    else:
        print("\033[91mAutentifikatsiya muvaffaqiyatsiz.\033[0m")
        await client.disconnect()
        sys.exit(1)

    return client


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
    """Main entry point for headless TeleExport server.

    Flow:
    1. Setup directories and load config
    2. Create client with correct session path
    3. Try to connect - if authorized, go to daemon mode
    4. If not authorized, run interactive auth (which handles session cleanup internally)
    """
    # Setup directories
    setup_dirs()

    # Load config
    config = load_config()
    api_id = config["api_id"]
    api_hash = config["api_hash"]

    print("\033[96m[TeleExport] Starting...\033[0m")
    print("\033[96m[DEBUG] Config loaded - api_id: {}\033[0m".format(api_id))
    print("\033[96m[DEBUG] Session dir: {}\033[0m".format(SESSION_DIR))

    # Create client and try to connect with existing session
    client = TeleExportClient(session_name="server")
    await client.init(api_id, api_hash)

    print("\033[96m[DEBUG] Session file path: {}.session\033[0m".format(client.session_path))

    is_authorized = await client.connect()

    if is_authorized:
        # Already authenticated - go straight to daemon mode
        me = await client.get_me()
        print("\033[92m[TeleExport] Session active for: {} {}\033[0m".format(
            me.first_name or "",
            me.last_name or ""
        ).strip())
    else:
        # Need interactive auth
        if not sys.stdin.isatty():
            print("\033[91mError: No active session and stdin is not a terminal.\033[0m")
            print("Run this script manually first to complete authentication:")
            print("  python3 {}".format(Path(__file__).resolve()))
            await client.disconnect()
            sys.exit(1)

        # Disconnect the current client - interactive_auth will create a fresh one
        # after cleaning session files
        await client.disconnect()

        # interactive_auth handles: clean sessions -> create client -> init -> connect -> auth
        client = await interactive_auth(api_id, api_hash)

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
