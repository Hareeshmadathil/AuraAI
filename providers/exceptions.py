"""Provider-layer errors with safe messages and no prompt contents."""

from typing import Any

from core.exceptions import ProviderError


class ProviderUnavailableError(ProviderError):
    """Raised when a configured provider cannot serve a capability."""


class ProviderValidationError(ProviderError):
    """Raised when provider output fails typed or safety validation."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(
            message,
            provider_name=provider_name,
            details=details,
            retryable=retryable,
        )


class ProviderRateLimitError(ProviderError):
    """Raised when an in-memory request limit is exceeded."""


class ProviderAuthenticationError(ProviderError):
    """Raised for a rejected provider credential without exposing it."""

    default_error_code = "PROVIDER_AUTHENTICATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(
            message,
            provider_name=provider_name,
            details=details,
            retryable=retryable,
        )


class ProviderTimeoutError(ProviderError):
    """Raised when a provider transport exceeds its timeout."""

    default_error_code = "PROVIDER_TIMEOUT_ERROR"


class ProviderSafetyError(ProviderError):
    """Raised when provider content fails a safety boundary."""

    default_error_code = "PROVIDER_SAFETY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(
            message,
            provider_name=provider_name,
            details=details,
            retryable=retryable,
        )
