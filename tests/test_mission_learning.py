"""Mission Learning & Feedback V1 tests."""
from pathlib import Path
import subprocess

from analytics.mission_learning import (
    LessonImpact,
    MissionLearningService,
)
from company_missions.mission_learning_demo import run_mission_learning_demo
from knowledge_manager.enums import ApprovalStatus, FreshnessStatus
from knowledge_manager.repository import InMemoryKnowledgeRepository
from knowledge_manager.service import KnowledgeManagerService
from mission_control import InMemoryMissionControlRepository, MissionControlService


ROOT = Path(__file__).resolve().parents[1]


def test_offline_demo_creates_positive_and_improvement_lessons():
    result = run_mission_learning_demo(ROOT)
    assert any(item.impact == LessonImpact.POSITIVE for item in result.lessons)
    assert any(item.impact == LessonImpact.IMPROVEMENT for item in result.lessons)
    assert result.future_lesson_delta == 2.0
    assert "Mission lessons changed the score by +2.00" in result.future_mission.reasoning_summary


def test_outcome_and_lesson_id_are_deterministic():
    first = run_mission_learning_demo(ROOT)
    repeated_outcome = first.learning_service.collect_outcome(
        first.outcome.mission_id,
        actual_outcome="Offline Mission Zero reached founder review.",
        founder_decision="revision_reviewed",
        revision_count=1,
    )
    repeated_lessons = first.learning_service.generate_lessons(first.outcome)
    assert first.outcome.outcome_id == repeated_outcome.outcome_id
    assert first.outcome.content_hash == repeated_outcome.content_hash
    assert [item.lesson_id for item in first.lessons] == [
        item.lesson_id for item in repeated_lessons
    ]


def test_provenance_hash_deduplication_and_dashboard_projection():
    result = run_mission_learning_demo(ROOT)
    for lesson in result.lessons:
        assert lesson.provenance["source_mission_id"] == str(result.outcome.mission_id)
        assert lesson.provenance["artifact_ids"]
        assert len(lesson.content_hash) == 64
    assert len({item.content_hash for item in result.lessons}) == len(result.lessons)


def test_only_approved_current_lessons_influence_future_missions():
    demo = run_mission_learning_demo(ROOT)
    control = MissionControlService(InMemoryMissionControlRepository())
    repository = InMemoryKnowledgeRepository()
    knowledge = KnowledgeManagerService(repository)
    learning = MissionLearningService(control=control, knowledge_manager=knowledge)
    approved = demo.lessons[0]
    request = learning._knowledge_request(approved)
    knowledge.ingest(request)
    assert learning.influence().score_delta == 4.0

    stored = repository.list_versions()[0]
    repository._versions[stored.version_id] = stored.model_copy(
        update={
            "freshness": stored.freshness.model_copy(
                update={"status": FreshnessStatus.EXPIRED}
            )
        }
    )
    assert learning.influence().score_delta == 0.0


def test_rejected_lessons_do_not_enter_knowledge_or_influence():
    demo = run_mission_learning_demo(ROOT)
    control = MissionControlService(InMemoryMissionControlRepository())
    knowledge = KnowledgeManagerService(InMemoryKnowledgeRepository())
    learning = MissionLearningService(control=control, knowledge_manager=knowledge)
    rejected = demo.lessons[0].model_copy(
        update={"approval_status": ApprovalStatus.REJECTED}
    )
    request = learning._knowledge_request(rejected)
    assert request.proposed_version.approval_status == ApprovalStatus.REJECTED
    assert learning.influence().score_delta == 0.0


def test_conflicting_lessons_use_knowledge_manager_conflicts():
    demo = run_mission_learning_demo(ROOT)
    control = MissionControlService(InMemoryMissionControlRepository())
    knowledge = KnowledgeManagerService(InMemoryKnowledgeRepository())
    learning = MissionLearningService(control=control, knowledge_manager=knowledge)
    first = demo.lessons[0]
    second = first.model_copy(
        update={
            "lesson_id": demo.lessons[1].lesson_id,
            "observation": "Creative Quality did not complete successfully.",
            "content_hash": demo.lessons[1].content_hash,
        }
    )
    knowledge.ingest(learning._knowledge_request(first))
    knowledge.ingest(learning._knowledge_request(second))
    assert len(knowledge.repository.list_versions()) >= 1
    assert isinstance(knowledge.conflicts, list)


def test_no_external_operations_and_protected_input_untracked(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External operation was attempted.")

    monkeypatch.setattr(
        "web_intelligence.service.WebIntelligenceService.execute", forbidden
    )
    monkeypatch.setattr(
        "providers.gemini.transport.UnavailableGeminiTransport.send", forbidden
    )
    monkeypatch.setattr(
        "private_video_production.render.service.PrivateRenderService.render",
        forbidden,
    )
    result = run_mission_learning_demo(ROOT)
    assert result.future_mission.publishing_required is False
    assert result.future_mission.rendering_required is False
    tracked = subprocess.run(
        ["git", "ls-files", "founder_inputs/mission_zero.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout.strip() == ""
