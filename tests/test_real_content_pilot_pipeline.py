"""End-to-end deterministic pilot pipeline tests."""

from company_missions.real_content_pilot import (
    RealContentPilot,
    RealContentPilotResult,
    TypedPilotArtifactStore,
    create_sample_real_content_pilot_input,
)
from core import AgentStatus
from mission_engine import MissionExecutionStatus


def test_deterministic_pipeline_reaches_founder_review_in_order() -> None:
    pilot = RealContentPilot()
    operation = pilot.run(create_sample_real_content_pilot_input())
    assert operation.success
    result = RealContentPilotResult.model_validate(
        operation.data["real_content_pilot_result"]
    )

    assert result.mission.status == MissionExecutionStatus.FOUNDER_REVIEW
    assert [item.stage for item in result.stage_results] == [
        MissionExecutionStatus.PLANNING,
        MissionExecutionStatus.RESEARCH,
        MissionExecutionStatus.SEO,
        MissionExecutionStatus.SCRIPT,
        MissionExecutionStatus.SCRIPT,
        MissionExecutionStatus.FOUNDER_REVIEW,
    ]
    assert len(result.mission.produced_artifacts) >= 5
    assert all(employee.current_task is None for employee in pilot.employees)
    assert all(employee.status == AgentStatus.IDLE for employee in pilot.employees)
    actions = [entry.action for entry in result.mission.history]
    assert "employee_assigned" in actions
    assert "artifact_registered" in actions


def test_artifact_failure_preserves_completed_partial_output() -> None:
    class FailingSecondRegistration(TypedPilotArtifactStore):
        def register(self, artifact) -> None:
            if len(self.list_all()) == 1:
                raise RuntimeError("injected artifact failure")
            super().register(artifact)

    store = FailingSecondRegistration()
    result = RealContentPilot(artifact_store=store).run(
        create_sample_real_content_pilot_input()
    )

    assert not result.success
    assert "research_artifact" in result.data["partial_artifacts"]
    assert len(store.list_all()) == 1
