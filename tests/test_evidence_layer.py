"""Canonical Evidence Layer V1 tests."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from agents.executive import AuraCEO
from agents.specialists.trend_hunter import TrendHunter
from company_missions.mission_generator import MissionGenerator
from intelligence_director.service import IntelligenceDirectorService
from mission_control import InMemoryMissionControlRepository, MissionControlService
from web_intelligence.evidence_layer import EvidenceDraft, EvidenceLayer


NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


class KnowledgeStub:
    def query(self, query):
        return SimpleNamespace(matches=[])


def draft(
    *,
    source="https://example.com/evidence",
    category="official_primary",
    observed_at=NOW,
    confidence=0.9,
    topic="Evidence-backed education",
    claim="Evidence supports an offline educational pilot.",
    provenance=None,
    contradictions=None,
):
    return EvidenceDraft(
        public_source=source,
        source_title="Evidence fixture",
        source_category=category,
        observed_at=observed_at,
        confidence=confidence,
        topic=topic,
        entities=["AuraAI"],
        claim=claim,
        excerpt="Bounded deterministic evidence excerpt.",
        freshness_category="general",
        provenance=provenance or {"fixture": "evidence-v1", "offline": True},
        contradicts_claims=contradictions or [],
    )


def test_evidence_ranking_uses_authority_and_confidence():
    layer = EvidenceLayer(now=NOW)
    ranked = layer.build(
        [
            draft(source="https://example.com/low", category="anonymous", confidence=0.3, topic="Low"),
            draft(source="https://example.com/high", category="official_primary", confidence=0.95, topic="High"),
        ]
    )
    assert [item.topic for item in ranked] == ["High", "Low"]
    assert ranked[0].source_authority.authority_score == 95


def test_material_contradiction_is_preserved_and_penalized():
    layer = EvidenceLayer(now=NOW)
    clean = layer.build([draft(source="https://example.com/clean")])[0]
    conflict = layer.build(
        [
            draft(
                source="https://example.com/conflict",
                contradictions=["Evidence does not support this pilot."],
            )
        ]
    )[0]
    assert conflict.contradictions[0].blocks_content_production is True
    assert conflict.rank_score < clean.rank_score


def test_freshness_decay_reduces_rank():
    value = draft(observed_at=NOW - timedelta(hours=12))
    fresh = EvidenceLayer(now=NOW).build([value])[0]
    expired = EvidenceLayer(now=NOW + timedelta(days=4)).build([value])[0]
    assert fresh.freshness.status != expired.freshness.status
    assert expired.rank_score < fresh.rank_score


def test_duplicate_removal_and_provenance_preservation():
    layer = EvidenceLayer(now=NOW)
    original = draft(provenance={"adapter": "fixture", "request_id": "one"})
    duplicate = original.model_copy(
        update={"provenance": {"adapter": "fixture", "request_id": "two"}}
    )
    result = layer.build([original, duplicate])
    assert len(result) == 1
    assert result[0].provenance == original.provenance
    assert result[0].citation.evidence_id == result[0].evidence_id
    assert len(result[0].content_hash) == 64


def test_mission_generator_consumes_evidence_and_stores_mission():
    repository = InMemoryMissionControlRepository()
    control = MissionControlService(repository)
    generator = MissionGenerator(
        control=control,
        trend_hunter=TrendHunter(),
        intelligence_director=IntelligenceDirectorService(),
        knowledge_manager=KnowledgeStub(),
        ceo=AuraCEO(),
        evidence_layer=EvidenceLayer(now=NOW),
    )
    mission = generator.generate("Grow AuraAI.")
    assert mission.title == "Grow AuraAI: practical education"
    assert repository.get_mission(mission.mission_id) == mission
    assert mission.offline_execution is True
    assert mission.publishing_required is False
    assert mission.rendering_required is False


def test_evidence_generation_never_executes_external_boundaries(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External execution was attempted.")

    monkeypatch.setattr(
        "web_intelligence.service.WebIntelligenceService.execute", forbidden
    )
    monkeypatch.setattr(
        "providers.gemini.transport.UnavailableGeminiTransport.send", forbidden
    )
    layer = EvidenceLayer(now=NOW)
    evidence = layer.fixtures("Grow AuraAI.")
    assert evidence
    assert all(item.provenance["offline"] is True for item in evidence)
