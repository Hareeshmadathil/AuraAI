"""In-memory provider usage metadata; no billing or persistence."""

from __future__ import annotations

from providers.models import ProviderUsage


class ProviderUsageTracker:
    """Collect usage records explicitly in memory."""

    def __init__(self) -> None:
        self._records: list[ProviderUsage] = []

    def record(self, usage: ProviderUsage) -> None:
        self._records.append(usage)

    def list_usage(self) -> tuple[ProviderUsage, ...]:
        return tuple(self._records)

    def total_requests(self) -> int:
        return len(self._records)
