from uuid import uuid4

from analytics.business_intelligence import BusinessIntelligenceService, DeterministicBusinessMetricsAdapter
from analytics.mission_learning import MissionLearningService
from knowledge_manager.repository import InMemoryKnowledgeRepository
from knowledge_manager.service import KnowledgeManagerService
from mission_control import InMemoryMissionControlRepository, MissionControlService


def test_business_metrics_are_canonical_deterministic_and_feed_learning():
    mission_id = uuid4()
    adapter = DeterministicBusinessMetricsAdapter()
    first = adapter.collect(mission_id)
    assert first == adapter.collect(mission_id)
    assert first.revenue == 175 and first.rpm == 7.5 and first.cpm == 11.2
    lesson = BusinessIntelligenceService().lesson(first)
    knowledge = KnowledgeManagerService(InMemoryKnowledgeRepository())
    learning = MissionLearningService(
        control=MissionControlService(InMemoryMissionControlRepository()),
        knowledge_manager=knowledge,
    )
    assert learning.store_approved_lesson(lesson)
    influence = learning.influence()
    assert influence.score_delta == 4.0
    assert lesson.lesson_id in influence.lesson_ids
