"""Thumbnail Designer concept tests."""

from agents.specialists import ThumbnailDesigner
from company_missions.fixtures import create_sample_production_input
from core import AgentStatus, TaskRecord
from production.content_brief import ContentBriefBuilder
from production.models import ThumbnailPlan
from production.script_engine import ScriptEngine


def test_thumbnail_designer_creates_truthful_mobile_concepts() -> None:
    brief = ContentBriefBuilder().build(create_sample_production_input())
    script = ScriptEngine().build(brief)
    designer = ThumbnailDesigner()
    task = TaskRecord(
        title="Design concepts",
        input_data={"content_brief": brief, "video_script": script},
    )
    designer.accept_task(task)
    result = designer.execute_current_task()
    plan = ThumbnailPlan.model_validate(result.data["thumbnail_plan"])
    assert len(plan.concepts) >= 3
    assert plan.recommended_concept_id in {
        concept.concept_id for concept in plan.concepts
    }
    assert all(len(concept.primary_text.split()) <= 4 for concept in plan.concepts)
    assert all("guarantee" not in concept.primary_text.casefold() for concept in plan.concepts)
    designer.clear_current_task()
    assert designer.status == AgentStatus.IDLE
