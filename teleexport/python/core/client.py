"""TeleExport Telegram client wrapper around Telethon."""
from pathlib import Path
from telethon import TelegramClient
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

    async def send_code(self, phone: str, force_sms: bool = False):
        """Send verification code to phone number.

        Args:
            phone: Phone number with country code.
            force_sms: If True, forces SMS delivery (only works as resend
                       after a previous send_code_request call).
        """
        return await self.client.send_code_request(phone, force_sms=force_sms)

    async def resend_code(self, phone: str):
        """Resend verification code via SMS using force_sms=True.

        This MUST be called after an initial send_code() call. Telethon
        requires a prior send_code_request to have been made for force_sms
        to trigger SMS delivery.
        """
        return await self.client.send_code_request(phone, force_sms=True)

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
