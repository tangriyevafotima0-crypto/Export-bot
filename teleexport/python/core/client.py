"""TeleExport Telegram client wrapper around Telethon."""
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.auth import ResendCodeRequest
from .config import SESSION_DIR


class TeleExportClient:
    """Wrapper around TelegramClient with simplified interface."""

    def __init__(self, session_name: str = "default"):
        # Telethon appends .session automatically, so pass path WITHOUT extension
        self.session_path = SESSION_DIR / session_name
        self.client: TelegramClient | None = None
        self._connected = False

    async def init(self, api_id: int, api_hash: str):
        """Initialize the Telethon client.

        If client already exists, disconnect it first to avoid conflicts.
        """
        if self.client is not None and self._connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self._connected = False

        self.client = TelegramClient(
            str(self.session_path),
            api_id,
            api_hash,
            device_model="TeleExport Desktop",
            system_version="1.0.0",
            app_version="1.0.0",
            lang_code="en",
            system_lang_code="en",
        )

    async def connect(self) -> bool:
        """Connect without logging in. Returns True if already authorized."""
        await self.client.connect()
        self._connected = True
        return await self.client.is_user_authorized()

    async def send_code(self, phone: str):
        """Send verification code to phone number.

        Args:
            phone: Phone number with country code.
        """
        return await self.client.send_code_request(phone)

    async def resend_code_sms(self, phone: str, phone_code_hash: str):
        """Resend verification code via SMS using the raw ResendCodeRequest API.

        This uses the Telethon raw API to trigger the next available delivery
        method (usually SMS). The deprecated force_sms parameter no longer works
        in newer Telethon versions, so we use ResendCodeRequest directly.

        MUST be called after an initial send_code() call on the same connection.

        Args:
            phone: Phone number with country code.
            phone_code_hash: The phone_code_hash from the initial send_code result.

        Returns:
            SentCode object with the new delivery type info.
        """
        return await self.client(ResendCodeRequest(
            phone_number=phone,
            phone_code_hash=phone_code_hash,
        ))

    async def sign_in(self, phone: str, code: str, phone_code_hash: str):
        """Sign in with the verification code."""
        return await self.client.sign_in(
            phone, code, phone_code_hash=phone_code_hash
        )

    async def sign_in_with_password(self, password: str):
        """Sign in with 2FA password."""
        return await self.client.sign_in(password=password)

    async def get_me(self):
        """Get current user info."""
        return await self.client.get_me()

    async def disconnect(self):
        """Disconnect the client gracefully."""
        if self.client and self._connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self._connected = False
