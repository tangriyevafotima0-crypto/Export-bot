"""Custom exception classes for the Anti-Stalker Intelligence System.

Provides a hierarchy of exceptions for clear error handling across modules.
"""


class StalkerBotError(Exception):
    """Base exception for all Anti-Stalker Intelligence System errors."""

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        self.message = message
        super().__init__(self.message)


class DatabaseError(StalkerBotError):
    """Raised when a database operation fails."""

    def __init__(self, message: str = "Database operation failed") -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)


class TelegramConnectionError(StalkerBotError):
    """Raised when connection to Telegram fails."""

    def __init__(self, message: str = "Failed to connect to Telegram") -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)


class ConfigurationError(StalkerBotError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str = "Configuration error") -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)


class RateLimitError(StalkerBotError):
    """Raised when a rate limit is hit."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)


class AuthenticationError(StalkerBotError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)
