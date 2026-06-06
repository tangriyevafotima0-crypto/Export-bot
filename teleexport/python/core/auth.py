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

    async def send_code(self, phone: str, api_id: int, api_hash: str) -> dict:
        """Send verification code to the phone number.

        First call sends the code to the Telegram app. Use resend_code()
        after this to trigger SMS delivery via the raw ResendCodeRequest API.

        Args:
            phone: Phone number with country code.
            api_id: Telegram API ID.
            api_hash: Telegram API hash.
        """
        self._phone = phone

        # Initialize client if not already done
        if self.client.client is None:
            await self.client.init(api_id, api_hash)
            await self.client.connect()

        result = await self.client.send_code(phone)
        self._phone_code_hash = result.phone_code_hash
        timeout = getattr(result, "timeout", 60) or 60
        code_type = type(result.type).__name__ if result.type else "Unknown"

        return {
            "phone_code_hash": result.phone_code_hash,
            "timeout": timeout,
            "code_type": code_type,
        }

    async def resend_code(self, phone: str, api_id: int, api_hash: str) -> dict:
        """Resend verification code via SMS using the raw ResendCodeRequest API.

        This uses the Telethon raw API (ResendCodeRequest) which triggers the
        next available delivery method (usually SMS). The deprecated force_sms
        parameter no longer works in newer Telethon versions.

        MUST be called AFTER an initial send_code() on the same connection.
        Requires the phone_code_hash from the initial send_code result.
        """
        self._phone = phone

        # Client must already be initialized (from previous send_code call)
        if self.client.client is None:
            await self.client.init(api_id, api_hash)
            await self.client.connect()

        if not self._phone_code_hash:
            # Instead of raising, attempt a fresh send_code to recover
            result = await self.send_code(phone, api_id, api_hash)
            return result

        # Use the raw ResendCodeRequest API for SMS delivery
        result = await self.client.resend_code_sms(phone, self._phone_code_hash)
        self._phone_code_hash = result.phone_code_hash
        timeout = getattr(result, "timeout", 60) or 60
        code_type = type(result.type).__name__ if result.type else "Unknown"

        return {
            "phone_code_hash": result.phone_code_hash,
            "timeout": timeout,
            "code_type": code_type,
        }

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
