from agents.specialists import HookArchitect
from company_missions import create_review_ready_production_package
from core import AgentStatus, TaskRecord
from creative_quality.models import HookAnalysis


def test_weak_and_clickbait_hook_is_improved_truthfully() -> None:
    script = create_review_ready_production_package().script.model_copy(
        update={"hook": "In this video, discover the guaranteed secret they hide."}
    )
    employee = HookArchitect()
    task = TaskRecord(title="Review hook", input_data={"video_script": script})
    employee.accept_task(task)
    result = employee.execute_current_task()
    analysis = HookAnalysis.model_validate(result.data["hook_analysis"])
    assert result.success
    assert analysis.weaknesses
    assert analysis.improved_hook != analysis.original_hook
    assert "guarantee" not in analysis.improved_hook.lower()
    assert analysis.claims_requiring_verification
    employee.clear_current_task()
    assert employee.current_task is None
    assert employee.status == AgentStatus.IDLE
