"""Content-only founder review actions for the first mission."""

from core import ValidationError
from runtime_engine.models import RuntimeEventType
from company_missions.real_content_pilot.models import RealContentPilotResult

from company_missions.first_real_content.models import FirstContentMissionResult
from company_missions.first_real_content.runner import FirstRealContentMissionRunner


class FirstContentFounderReviewService:
    """Delegate review to the existing founder gate without delivery approval."""

    def __init__(self, runner: FirstRealContentMissionRunner) -> None:
        self._runner = runner

    def approve_content(
        self, result: FirstContentMissionResult, notes: str
    ) -> FirstContentMissionResult:
        if result.production_review.blocking_issues:
            raise ValidationError(
                "Content blockers prevent founder approval.",
                error_code="CONTENT_BLOCKERS_PREVENT_APPROVAL",
            )
        pilot = self._runner.pilot.founder_review.approve(result.pilot, notes=notes)
        self._runner._emit(RuntimeEventType.FOUNDER_CONTENT_APPROVED)
        self._runner._emit(RuntimeEventType.FIRST_CONTENT_MISSION_COMPLETED)
        return self._with_updated_mission(result, pilot)

    def reject_content(
        self, result: FirstContentMissionResult, reason: str
    ) -> FirstContentMissionResult:
        pilot = self._runner.pilot.founder_review.reject(result.pilot, reason=reason)
        self._runner._emit(RuntimeEventType.FOUNDER_CONTENT_REJECTED)
        return self._with_updated_mission(result, pilot)

    def request_content_revision(
        self, result: FirstContentMissionResult, notes: str
    ) -> FirstContentMissionResult:
        pilot = self._runner.pilot.founder_review.request_revision(result.pilot, notes=notes)
        self._runner._emit(RuntimeEventType.FOUNDER_CONTENT_REVISION_REQUESTED)
        return self._with_updated_mission(result, pilot)

    @staticmethod
    def _with_updated_mission(
        result: FirstContentMissionResult,
        pilot: RealContentPilotResult,
    ) -> FirstContentMissionResult:
        mission = pilot.mission
        summary = result.mission_summary.model_copy(
            update={
                "current_state": mission.status,
                "founder_approval": mission.founder_approval_state.value,
                "progress_percentage": mission.progress_percentage,
                "artifact_count": len(mission.produced_artifacts),
            }
        )
        return result.model_copy(
            update={"pilot": pilot, "mission": mission, "mission_summary": summary}
        )
