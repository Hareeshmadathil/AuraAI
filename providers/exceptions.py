"""Provider-layer errors with safe messages and no prompt contents."""

from core.exceptions import ProviderError


class ProviderUnavailableError(ProviderError):
    """Raised when a configured provider cannot serve a capability."""


class ProviderValidationError(ProviderError):
    """Raised when provider output fails typed or safety validation."""


class ProviderRateLimitError(ProviderError):
    """Raised when an in-memory request limit is exceeded."""
