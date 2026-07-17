"""Capability Phase 1 canonical evidence provider tests."""
from web_intelligence.evidence_layer import CanonicalEvidence
from web_intelligence.evidence_providers import (
    Crawl4AIEvidenceAdapter, DeterministicEvidenceAdapter,
    EvidenceAdapterRegistry, EvidenceFeatureFlags,
)


def test_offline_is_default_and_normalized():
    registry = EvidenceAdapterRegistry([DeterministicEvidenceAdapter(), Crawl4AIEvidenceAdapter()])
    evidence = registry.collect("Grow AuraAI")
    assert evidence and all(isinstance(item, CanonicalEvidence) for item in evidence)
    assert all(item.content_hash and item.citation.url and 0 <= item.confidence <= 1 for item in evidence)


def test_unavailable_live_provider_falls_back_without_execution():
    registry = EvidenceAdapterRegistry([DeterministicEvidenceAdapter(), Crawl4AIEvidenceAdapter()])
    evidence = registry.collect("Grow AuraAI", EvidenceFeatureFlags(live_evidence_enabled=True))
    assert evidence[0].provenance["offline"] is True
    assert registry.health()[0].provider.value == "crawl4ai"


def test_injected_provider_must_return_canonical_evidence():
    offline = DeterministicEvidenceAdapter()
    expected = offline.collect("Grow AuraAI")
    adapter = Crawl4AIEvidenceAdapter(lambda goal: expected)
    registry = EvidenceAdapterRegistry([offline, adapter])
    actual = registry.collect("Grow AuraAI", EvidenceFeatureFlags(live_evidence_enabled=True))
    assert actual == expected
