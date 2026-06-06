"""Tests for the AuthManager."""
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from python.core.auth import AuthManager
from python.core.client import TeleExportClient


@pytest.fixture
def mock_client():
    """Create a mock TeleExportClient."""
    client = MagicMock(spec=TeleExportClient)
    client.client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.get_me = AsyncMock(return_value=MagicMock(
        id=12345,
        first_name="Test",
        last_name="User",
        username="testuser",
        phone="1234567890",
    ))
    client.send_code = AsyncMock(return_value=MagicMock(
        phone_code_hash="abc123",
        timeout=60,
        type=MagicMock(__class__=type("SentCodeTypeSms", (), {})),
    ))
    client.resend_code_sms = AsyncMock(return_value=MagicMock(
        phone_code_hash="abc456",
        timeout=60,
        type=MagicMock(__class__=type("SentCodeTypeSms", (), {})),
    ))
    client.sign_in = AsyncMock(return_value=MagicMock(
        id=12345,
        first_name="Test",
        last_name="User",
        username="testuser",
        phone="1234567890",
    ))
    client.init = AsyncMock()
    return client


@pytest.fixture
def auth_manager(mock_client):
    """Create an AuthManager with a mock client."""
    return AuthManager(mock_client)


class TestCheckSession:
    """Tests for check_session method."""

    @pytest.mark.asyncio
    async def test_no_session_when_client_is_none(self):
        """Test check_session returns has_session=False when client is None."""
        client = MagicMock(spec=TeleExportClient)
        client.client = None
        auth = AuthManager(client)

        result = await auth.check_session()
        assert result == {"has_session": False}

    @pytest.mark.asyncio
    async def test_session_exists_and_authorized(self, auth_manager, mock_client):
        """Test check_session when session exists and user is authorized."""
        result = await auth_manager.check_session()
        assert result["has_session"] is True
        assert result["phone_hint"] == "7890"

    @pytest.mark.asyncio
    async def test_session_exists_but_not_authorized(self, mock_client):
        """Test check_session when connect returns False (not authorized)."""
        mock_client.connect = AsyncMock(return_value=False)
        auth = AuthManager(mock_client)

        result = await auth.check_session()
        assert result == {"has_session": False}

    @pytest.mark.asyncio
    async def test_session_check_exception(self, mock_client):
        """Test check_session returns False on exception."""
        mock_client.connect = AsyncMock(side_effect=Exception("Connection failed"))
        auth = AuthManager(mock_client)

        result = await auth.check_session()
        assert result == {"has_session": False}


class TestAuthFlowTransitions:
    """Tests for auth flow state transitions."""

    @pytest.mark.asyncio
    async def test_send_code(self, auth_manager, mock_client):
        """Test send_code sends verification code and returns hash/timeout."""
        result = await auth_manager.send_code("1234567890", 12345, "hash123")

        assert result["phone_code_hash"] == "abc123"
        assert result["timeout"] == 60
        # client.client is already set (not None), so init/connect are skipped
        mock_client.send_code.assert_awaited_once_with("1234567890")

    @pytest.mark.asyncio
    async def test_send_code_initializes_when_client_is_none(self, mock_client):
        """Test send_code initializes client when client.client is None."""
        mock_client.client = None
        auth = AuthManager(mock_client)

        result = await auth.send_code("1234567890", 12345, "hash123")

        assert result["phone_code_hash"] == "abc123"
        mock_client.init.assert_awaited_once_with(12345, "hash123")
        mock_client.connect.assert_awaited()

    @pytest.mark.asyncio
    async def test_send_code_stores_phone(self, auth_manager):
        """Test send_code stores the phone number."""
        await auth_manager.send_code("9876543210", 12345, "hash")
        assert auth_manager._phone == "9876543210"

    @pytest.mark.asyncio
    async def test_sign_in_success(self, auth_manager, mock_client):
        """Test successful sign_in."""
        result = await auth_manager.sign_in("1234567890", "12345", "hash")

        assert result["success"] is True
        assert result["user"]["id"] == 12345
        assert result["user"]["first_name"] == "Test"
        assert result["user"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_sign_in_needs_2fa(self, auth_manager, mock_client):
        """Test sign_in when 2FA is required."""
        mock_client.sign_in = AsyncMock(
            side_effect=Exception("SessionPasswordNeeded")
        )

        result = await auth_manager.sign_in("1234567890", "12345", "hash")
        assert result["success"] is False
        assert result["requires_2fa"] is True

    @pytest.mark.asyncio
    async def test_sign_in_propagates_other_errors(self, auth_manager, mock_client):
        """Test sign_in raises non-2FA exceptions."""
        mock_client.sign_in = AsyncMock(
            side_effect=Exception("PhoneNumberInvalid")
        )

        with pytest.raises(Exception, match="PhoneNumberInvalid"):
            await auth_manager.sign_in("invalid", "12345", "hash")
