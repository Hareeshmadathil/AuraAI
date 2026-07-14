"""End-to-end deterministic runner tests."""

from company_missions.first_real_content.dashboard import create_sample_first_content_input
from company_missions.first_real_content.runner import FirstRealContentMissionRunner
from mission_engine import MissionExecutionStatus


def test_runner_reaches_review_and_preserves_typed_packages() -> None:
    runner = FirstRealContentMissionRunner()
    result = runner.run_typed(create_sample_first_content_input())
    assert result.mission.status == MissionExecutionStatus.FOUNDER_REVIEW
    assert result.mission.founder_approval_state.value == "pending"
    assert result.production_review.rendered is False
    assert result.production_review.published is False
    assert result.production_package.package_id == result.production_review.package_id
    assert result.pilot.research_artifact.artifact_id
    assert result.pilot.seo_artifact.artifact_id
    assert result.pilot.script_artifact.artifact_id
    assert all(employee.status.value == "idle" for employee in runner.pilot.employees)


def test_runner_history_and_artifacts_precede_review() -> None:
    result = FirstRealContentMissionRunner().run_typed(create_sample_first_content_input())
    transitions = [
        entry.to_status
        for entry in result.mission.history
        if entry.action == "state_transition" and entry.to_status
    ]
    assert transitions[-1] == MissionExecutionStatus.FOUNDER_REVIEW
    assert transitions == [
        MissionExecutionStatus.CREATED,
        MissionExecutionStatus.PLANNING,
        MissionExecutionStatus.RESEARCH,
        MissionExecutionStatus.SEO,
        MissionExecutionStatus.SCRIPT,
        MissionExecutionStatus.FOUNDER_REVIEW,
    ]
    assert result.mission_summary.artifact_count >= 5
