"""Deterministic request limits with no sleeping or network behavior."""

from __future__ import annotations

from providers.exceptions import ProviderRateLimitError


class ProviderRateLimiter:
    """Bound requests per provider for one explicitly owned process lifetime."""

    def __init__(self, maximum_requests: int = 1000) -> None:
        if maximum_requests <= 0:
            raise ValueError("maximum_requests must be greater than zero.")
        self.maximum_requests = maximum_requests
        self._counts: dict[str, int] = {}

    def acquire(self, provider_name: str) -> None:
        count = self._counts.get(provider_name, 0)
        if count >= self.maximum_requests:
            raise ProviderRateLimitError(
                "Provider request limit reached.",
                provider_name=provider_name,
                retryable=True,
            )
        self._counts[provider_name] = count + 1

    def count(self, provider_name: str) -> int:
        return self._counts.get(provider_name, 0)
