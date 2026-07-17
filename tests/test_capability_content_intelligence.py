from intelligence_director.content_intelligence import ContentIntelligenceService
from intelligence_director.service import IntelligenceDirectorService
from web_intelligence.evidence_layer import EvidenceLayer
from agents.executive import AuraCEO
from agents.specialists.trend_hunter import TrendHunter
from company_missions.mission_generator import MissionGenerator
from mission_control import InMemoryMissionControlRepository, MissionControlService
from types import SimpleNamespace


def test_content_intelligence_is_structured_deterministic_and_provenanced():
    evidence = EvidenceLayer().fixtures("Grow AuraAI")
    service = ContentIntelligenceService()
    first = service.analyze(evidence)
    second = service.analyze(evidence)
    assert first == second
    assert first.evidence_ids == [item.evidence_id for item in evidence]
    assert first.patterns[0].hook and first.patterns[0].seo_terms
    assert 0 <= first.topic_saturation <= 100


def test_mission_generator_uses_content_intelligence():
    knowledge = SimpleNamespace(query=lambda query: SimpleNamespace(matches=[]))
    generator = MissionGenerator(
        control=MissionControlService(InMemoryMissionControlRepository()),
        trend_hunter=TrendHunter(), intelligence_director=IntelligenceDirectorService(),
        knowledge_manager=knowledge, ceo=AuraCEO(),
    )
    mission = generator.generate("Grow with content intelligence")
    assert "Content Intelligence:" in mission.reasoning_summary
    assert mission.rendering_required is False and mission.publishing_required is False
