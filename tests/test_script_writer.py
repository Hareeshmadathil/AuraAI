"""Deterministic script writer behavior tests."""

from agents.specialists import ScriptWriter
from company_missions.fixtures import create_sample_production_input
from core import AgentStatus, TaskRecord
from production.content_brief import ContentBriefBuilder
from production.models import VideoScript


def test_script_is_meaningful_aligned_and_lifecycle_cleans_up() -> None:
    value = create_sample_production_input()
    brief = ContentBriefBuilder().build(value)
    writer = ScriptWriter()
    task = TaskRecord(title="Write script", input_data={"content_brief": brief})
    writer.accept_task(task)
    result = writer.execute_current_task()
    script = VideoScript.model_validate(result.data["video_script"])
    assert result.success
    assert script.hook
    assert len(script.sections) >= 5
    assert script.total_estimated_duration_seconds == value.target_duration_seconds
    assert script.word_count == sum(len(item.narration.split()) for item in script.sections)
    assert value.primary_keyword.casefold() in (
        script.title + " " + " ".join(item.narration for item in script.sections)
    ).casefold()
    assert any(item.claims_requiring_verification for item in script.sections)
    assert "guaranteed revenue" not in " ".join(
        item.narration.casefold() for item in script.sections
    )
    writer.clear_current_task()
    assert writer.status == AgentStatus.IDLE
    assert writer.current_task is None


def test_script_writer_rejects_missing_brief() -> None:
    writer = ScriptWriter()
    task = TaskRecord(title="Missing brief")
    writer.accept_task(task)
    assert not writer.execute_current_task().success
    writer.clear_current_task()
