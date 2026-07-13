"""Marketing Director for AuraAI Creator OS."""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from core import (
    DepartmentName,
    MissionRecord,
    OperationResult,
    TaskRecord,
    ValidationError,
)
from marketing.marketing_models import MarketingPlan
from marketing.marketing_strategy import (
    build_marketing_objectives,
    build_platform_assignments,
    expected_marketing_outputs,
)
from providers import PromptCategory, ProviderCapability, build_department_prompt


class MarketingDirector(BaseEmployee):
    """Director responsible for coordinated campaign planning."""

    def __init__(self) -> None:
        super().__init__(
            name="Echo",
            job_title="Marketing Director",
            department=DepartmentName.MARKETING,
            description=(
                "Creates approved cross-platform marketing plans, "
                "defines campaign positioning, and prepares platform "
                "assignments without publishing or creating accounts."
            ),
        )

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Create a marketing plan from a task's approved mission."""

        mission = self._require_mission(task.input_data)
        plan = self.create_marketing_plan(mission)
        generated_tasks = plan.to_task_records()
        provider_result = self.request_provider(
            ProviderCapability.MARKETING,
            build_department_prompt(
                "marketing_mission_advisory",
                PromptCategory.STRATEGY,
                mission.title,
            ),
        )

        return OperationResult.ok(
            "Marketing Director created the mission marketing plan.",
            data={
                "mission_id": str(mission.mission_id),
                "marketing_plan": plan.model_dump(mode="json"),
                "generated_tasks": [
                    generated_task.model_dump(mode="json")
                    for generated_task in generated_tasks
                ],
                **(
                    {"provider_advisory": provider_result.model_dump(mode="json")}
                    if provider_result is not None
                    else {}
                ),
            },
        )

    def create_marketing_plan(
        self,
        mission: MissionRecord,
    ) -> MarketingPlan:
        """Create a structured plan for an approved mission."""

        self._validate_mission(mission)
        assignments = build_platform_assignments()

        return MarketingPlan(
            mission_id=mission.mission_id,
            mission_title=mission.title,
            brand_positioning=(
                f"Position {mission.title} as a trustworthy, practical "
                "creator brand that turns complex audience needs into "
                "clear and useful content."
            ),
            content_pillars=[
                "Practical education",
                "Evidence-based insights",
                "Actionable examples",
                "Community questions and outcomes",
            ],
            audience_promise=(
                "Every published campaign asset will give the audience "
                "a clear insight or action without overstating results."
            ),
            campaign_goals=build_marketing_objectives(mission),
            platform_assignments=assignments,
            expected_outputs=expected_marketing_outputs(assignments),
            final_approval_required=True,
            created_by_agent_id=self.agent_id,
            created_by_name=self.name,
        )

    @staticmethod
    def _validate_mission(mission: MissionRecord) -> None:
        """Ensure a mission is eligible for marketing planning."""

        if mission.is_terminal:
            raise ValidationError(
                "A terminal mission cannot receive a marketing plan.",
                details={
                    "mission_id": str(mission.mission_id),
                    "status": mission.status.value,
                },
            )

        if not mission.is_approved:
            raise ValidationError(
                "The mission must be approved before marketing planning.",
                details={
                    "mission_id": str(mission.mission_id),
                    "approval_status": mission.approval_status.value,
                },
            )

        if not mission.objectives:
            raise ValidationError(
                "The mission requires measurable objectives before "
                "marketing planning.",
                details={"mission_id": str(mission.mission_id)},
            )

    @staticmethod
    def _require_mission(
        input_data: dict[str, Any],
    ) -> MissionRecord:
        """Extract and validate the mission supplied to the director."""

        mission_value = input_data.get("mission")

        if mission_value is None:
            raise ValidationError(
                "Marketing Director requires a mission in task.input_data.",
                details={"required_key": "mission"},
            )

        if isinstance(mission_value, MissionRecord):
            return mission_value

        if isinstance(mission_value, dict):
            try:
                return MissionRecord.model_validate(mission_value)
            except Exception as error:
                raise ValidationError(
                    "The supplied marketing mission is invalid.",
                    details={
                        "exception_type": error.__class__.__name__,
                    },
                ) from error

        raise ValidationError(
            "Marketing mission input must be a MissionRecord or dictionary.",
            details={
                "received_type": mission_value.__class__.__name__,
            },
        )
