#!/usr/bin/env python3
"""TeleExport headless server runner.

Standalone script that runs the TeleExport Python backend without Electron.
Handles authentication interactively on first run, then runs as a daemon service.
"""
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

# Ensure the teleexport directory is in the Python path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from python.core.config import setup_dirs, CONFIG_DIR, SESSION_DIR
from python.core.client import TeleExportClient
from python.core.auth import AuthManager


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
    """Handle interactive authentication flow."""
    print("\n\033[96m=== TeleExport Authentication ===\033[0m")
    print("No active session found. Starting authentication...\n")

    phone = input("\033[93mEnter your phone number (with country code, e.g. +1234567890): \033[0m").strip()
    if not phone:
        print("\033[91mError: Phone number cannot be empty.\033[0m")
        sys.exit(1)

    print("\033[96mSending verification code...\033[0m")
    result = await auth.send_code(phone, api_id, api_hash)
    phone_code_hash = result["phone_code_hash"]

    code = input("\033[93mEnter the verification code you received: \033[0m").strip()
    if not code:
        print("\033[91mError: Verification code cannot be empty.\033[0m")
        sys.exit(1)

    sign_in_result = await auth.sign_in(phone, code, phone_code_hash)

    if not sign_in_result.get("success"):
        if sign_in_result.get("requires_2fa"):
            print("\033[93mTwo-factor authentication required.\033[0m")
            password = input("\033[93mEnter your 2FA password: \033[0m").strip()
            if not password:
                print("\033[91mError: 2FA password cannot be empty.\033[0m")
                sys.exit(1)
            sign_in_result = await auth.sign_in_2fa(password)
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


async def run_daemon(client: TeleExportClient):
    """Run as a daemon, keeping the client connected."""
    print("\033[92m[TeleExport] Service running. Client connected and ready.\033[0m")
    print("[TeleExport] Press Ctrl+C to stop (or send SIGTERM).")

    stop_event = asyncio.Event()

    def handle_signal():
        print("\n\033[93m[TeleExport] Shutdown signal received...\033[0m")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    # Keep alive until signaled to stop
    await stop_event.wait()

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
            print("  python3.11 {}".format(Path(__file__).resolve()))
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
        sys.exit(1)
