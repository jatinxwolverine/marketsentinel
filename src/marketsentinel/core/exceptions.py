"""Custom exceptions hierarchy for MarketSentinel."""


class MarketSentinelError(Exception):
    """Base exception for all MarketSentinel application errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class APIConnectionError(MarketSentinelError):
    """Raised when an external market API fails or rate-limits."""
    pass


class DataProcessingError(MarketSentinelError):
    """Raised when data transformation, indicator calculation, or parsing fails."""
    pass


class StorageError(MarketSentinelError):
    """Raised when database operations or backups encounter errors."""
    pass


class ReportGenerationError(MarketSentinelError):
    """Raised when chart plotting or PDF compilation fails."""
    pass


class AlertDispatchError(MarketSentinelError):
    """Raised when dispatching notifications through webhooks/email/console fails."""
    pass


class ConfigurationError(MarketSentinelError):
    """Raised when application configuration is missing or invalid."""
    pass
