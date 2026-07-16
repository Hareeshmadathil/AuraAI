"""Offline Mission Zero learning and future-generation demonstration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.executive import AuraCEO
from agents.specialists.trend_hunter import TrendHunter
from analytics.mission_learning import MissionLearningService, MissionLesson, MissionOutcome
from company_missions.mission_generator import MissionGenerator
from company_missions.mission_zero_integration import MissionZeroIntegration
from intelligence_director.service import IntelligenceDirectorService
from knowledge_manager.repository import InMemoryKnowledgeRepository
from knowledge_manager.service import KnowledgeManagerService
from mission_control import InMemoryMissionControlRepository, MissionControlService
from mission_control.models import MissionRecord


@dataclass(frozen=True, slots=True)
class MissionLearningDemoResult:
    outcome: MissionOutcome
    lessons: tuple[MissionLesson, ...]
    future_mission: MissionRecord
    original_score: float
    future_lesson_delta: float
    learning_service: MissionLearningService


def run_mission_learning_demo(project_root: Path) -> MissionLearningDemoResult:
    """Run one offline mission, learn, and influence a future mission."""

    control = MissionControlService(InMemoryMissionControlRepository())
    knowledge = KnowledgeManagerService(InMemoryKnowledgeRepository())
    generator = MissionGenerator(
        control=control,
        trend_hunter=TrendHunter(),
        intelligence_director=IntelligenceDirectorService(),
        knowledge_manager=knowledge,
        ceo=AuraCEO(),
    )
    original = generator.generate("Grow AuraAI.")
    MissionZeroIntegration(control, project_root=project_root).run(original)
    learning = MissionLearningService(control=control, knowledge_manager=knowledge)
    outcome = learning.collect_outcome(
        original.mission_id,
        actual_outcome="Offline Mission Zero reached founder review.",
        founder_decision="revision_reviewed",
        revision_count=1,
    )
    lessons = learning.generate_lessons(outcome)
    learning.persist(outcome, lessons)
    future = generator.generate("Grow AuraAI with a second reviewed mission.")
    influence = learning.influence()
    return MissionLearningDemoResult(
        outcome=outcome,
        lessons=tuple(lessons),
        future_mission=future,
        original_score=original.mission_score,
        future_lesson_delta=influence.score_delta,
        learning_service=learning,
    )
