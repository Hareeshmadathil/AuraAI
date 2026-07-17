"""Canonical evidence provider adapters with deterministic fallback."""
from __future__ import annotations

from enum import StrEnum
from typing import Callable, Protocol

from pydantic import Field

from core import AuraBaseModel
from web_intelligence.evidence_layer import CanonicalEvidence, EvidenceLayer


class EvidenceProviderKind(StrEnum):
    DETERMINISTIC = "deterministic"
    CRAWL4AI = "crawl4ai"


class EvidenceFeatureFlags(AuraBaseModel):
    live_evidence_enabled: bool = False
    preferred_provider: EvidenceProviderKind = EvidenceProviderKind.CRAWL4AI
    fallback_enabled: bool = True


class EvidenceProviderHealth(AuraBaseModel):
    provider: EvidenceProviderKind
    available: bool
    live_enabled: bool
    healthy: bool
    reason: str


class EvidenceProviderAdapter(Protocol):
    kind: EvidenceProviderKind

    def health(self) -> EvidenceProviderHealth: ...
    def collect(self, founder_goal: str) -> list[CanonicalEvidence]: ...


class DeterministicEvidenceAdapter:
    kind = EvidenceProviderKind.DETERMINISTIC

    def __init__(self, layer: EvidenceLayer | None = None) -> None:
        self.layer = layer or EvidenceLayer()

    def health(self) -> EvidenceProviderHealth:
        return EvidenceProviderHealth(
            provider=self.kind, available=True, live_enabled=False, healthy=True,
            reason="Deterministic offline evidence is available.",
        )

    def collect(self, founder_goal: str) -> list[CanonicalEvidence]:
        return self.layer.fixtures(founder_goal)


class Crawl4AIEvidenceAdapter:
    """Injected Crawl4AI boundary; it never imports or launches a browser."""

    kind = EvidenceProviderKind.CRAWL4AI

    def __init__(
        self,
        collector: Callable[[str], list[CanonicalEvidence]] | None = None,
    ) -> None:
        self.collector = collector

    def health(self) -> EvidenceProviderHealth:
        available = self.collector is not None
        return EvidenceProviderHealth(
            provider=self.kind,
            available=available,
            live_enabled=available,
            healthy=available,
            reason=("Injected canonical Crawl4AI collector is ready." if available else
                    "Crawl4AI execution is unavailable; deterministic fallback required."),
        )

    def collect(self, founder_goal: str) -> list[CanonicalEvidence]:
        if self.collector is None:
            raise RuntimeError("Crawl4AI canonical collector is unavailable.")
        return [CanonicalEvidence.model_validate(item) for item in self.collector(founder_goal)]


class EvidenceAdapterRegistry:
    """Injected registry selecting canonical providers with safe fallback."""

    def __init__(self, adapters: list[EvidenceProviderAdapter]) -> None:
        self._adapters = {adapter.kind: adapter for adapter in adapters}

    def health(self) -> list[EvidenceProviderHealth]:
        return [self._adapters[key].health() for key in sorted(self._adapters)]

    def collect(
        self,
        founder_goal: str,
        flags: EvidenceFeatureFlags | None = None,
    ) -> list[CanonicalEvidence]:
        settings = flags or EvidenceFeatureFlags()
        offline = self._adapters.get(EvidenceProviderKind.DETERMINISTIC)
        selected = self._adapters.get(settings.preferred_provider)
        if settings.live_evidence_enabled and selected and selected.health().healthy:
            try:
                return selected.collect(founder_goal)
            except Exception:
                if not settings.fallback_enabled:
                    raise
        if offline is None:
            raise RuntimeError("Deterministic evidence adapter is not registered.")
        return offline.collect(founder_goal)


def create_default_evidence_registry() -> EvidenceAdapterRegistry:
    return EvidenceAdapterRegistry([
        DeterministicEvidenceAdapter(), Crawl4AIEvidenceAdapter(),
    ])
