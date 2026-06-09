"""JWT authentication for the FastAPI dashboard.

Provides token creation, verification, and dependency injection
for protecting dashboard API routes.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload data to encode in the token.
        expires_delta: Optional custom expiration duration.

    Returns:
        str: Encoded JWT token string.
    """
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.dashboard_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token string to verify.

    Returns:
        dict: Decoded payload data.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.dashboard_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency to extract and verify the current user from JWT.

    Args:
        credentials: HTTP Bearer credentials from the request.

    Returns:
        dict: Decoded user payload from the token.

    Raises:
        HTTPException: If credentials are missing or token is invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )
    return verify_token(credentials.credentials)
