"""Authentication manager for TeleExport."""
from .client import TeleExportClient
from .config import SESSION_DIR


class AuthManager:
    """Handles the full authentication flow."""

    def __init__(self, client: TeleExportClient):
        self.client = client
        self._phone: str | None = None
        self._phone_code_hash: str | None = None

    async def check_session(self) -> dict:
        """Check if a valid session exists."""
        if self.client.client is None:
            return {"has_session": False}

        try:
            is_authorized = await self.client.connect()
            if is_authorized:
                me = await self.client.get_me()
                phone_hint = me.phone[-4:] if me.phone else None
                return {
                    "has_session": True,
                    "phone_hint": phone_hint,
                    "user": {
                        "id": me.id,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                        "username": me.username,
                        "phone": me.phone,
                    },
                }
        except Exception:
            pass

        return {"has_session": False}

    async def send_code(self, phone: str, api_id: int, api_hash: str, force_sms: bool = False) -> dict:
        """Initialize client and send verification code.

        Args:
            phone: Phone number with country code.
            api_id: Telegram API ID.
            api_hash: Telegram API hash.
            force_sms: If True, forces SMS delivery instead of in-app code.
        """
        self._phone = phone

        if self.client.client is None:
            await self.client.init(api_id, api_hash)
            await self.client.connect()

        result = await self.client.send_code(phone, force_sms=force_sms)
        self._phone_code_hash = result.phone_code_hash
        timeout = getattr(result, "timeout", 60) or 60
        code_type = type(result.type).__name__ if result.type else "Unknown"

        return {
            "phone_code_hash": result.phone_code_hash,
            "timeout": timeout,
            "code_type": code_type,
        }

    async def resend_code(self, phone: str, api_id: int, api_hash: str) -> dict:
        """Resend verification code via SMS (force_sms=True).

        Use this when the user did not receive the code in the Telegram app.
        """
        return await self.send_code(phone, api_id, api_hash, force_sms=True)

    async def sign_in(self, phone: str, code: str, phone_code_hash: str) -> dict:
        """Sign in with the verification code."""
        try:
            user = await self.client.sign_in(phone, code, phone_code_hash)
            return {
                "success": True,
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "phone": user.phone,
                },
            }
        except Exception as e:
            error_msg = str(e)
            if "SessionPasswordNeeded" in error_msg or "Two" in error_msg:
                return {"success": False, "requires_2fa": True}
            raise

    async def check_2fa(self) -> dict:
        """Check if 2FA is required."""
        try:
            # If we can get_me, we're already logged in
            await self.client.get_me()
            return {"has_2fa": False}
        except Exception:
            return {"has_2fa": True, "hint": ""}

    async def sign_in_2fa(self, password: str) -> dict:
        """Sign in with 2FA password."""
        user = await self.client.sign_in_with_password(password)
        return {
            "success": True,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "phone": user.phone,
            },
        }

    async def logout(self) -> dict:
        """Log out and remove session."""
        if self.client.client:
            await self.client.client.log_out()
        return {"success": True}
