"""TeleExport Telegram client wrapper around Telethon."""
from pathlib import Path
from telethon import TelegramClient
from .config import SESSION_DIR


class TeleExportClient:
    """Wrapper around TelegramClient with simplified interface."""

    def __init__(self, session_name: str = "default"):
        self.session_path = SESSION_DIR / f"{session_name}.session"
        self.client: TelegramClient | None = None

    async def init(self, api_id: int, api_hash: str):
        """Initialize the Telethon client."""
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
        return await self.client.is_user_authorized()

    async def send_code(self, phone: str):
        """Send verification code to phone number."""
        return await self.client.send_code_request(phone)

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
        """Disconnect the client."""
        if self.client:
            await self.client.disconnect()
