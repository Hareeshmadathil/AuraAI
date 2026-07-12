"""
Workflow planning tools for AuraAI Creator OS.

The workflow planner converts an approved mission into a deterministic
operational plan. Specialized planners can later replace or extend this
generic planner for research, production, publishing, and analytics
missions without changing the COO interface.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import (
    ApprovalStatus,
    AuraBaseModel,
    DepartmentName,
    MissionRecord,
    ValidationError,
    get_logger,
    utc_now,
)
from workflows import BaseWorkflow


class WorkflowPlanStep(AuraBaseModel):
    """One planned operational step before workflow creation."""

    plan_step_id: UUID = Field(default_factory=uuid4)

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str = Field(
        default="",
        max_length=5000,
    )

    department: DepartmentName

    dependency_plan_step_ids: list[UUID] = Field(
        default_factory=list
    )

    requires_approval: bool = False

    maximum_retries: int = Field(
        default=3,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_dependencies(self) -> "WorkflowPlanStep":
        """Prevent a plan step from depending on itself."""

        if self.plan_step_id in self.dependency_plan_step_ids:
            raise ValueError(
                "A workflow plan step cannot depend on itself."
            )

        return self


class WorkflowPlan(AuraBaseModel):
    """Validated operational plan generated from one mission."""

    plan_id: UUID = Field(default_factory=uuid4)

    mission_id: UUID

    name: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str = Field(
        default="",
        max_length=5000,
    )

    lead_department: DepartmentName

    steps: list[WorkflowPlanStep] = Field(
        min_length=1,
    )

    created_at: datetime = Field(default_factory=utc_now)


class PlannedWorkflow(BaseWorkflow):
    """
    Concrete workflow created from a validated WorkflowPlan.
    """

    def __init__(
        self,
        *,
        plan: WorkflowPlan,
    ) -> None:
        self.plan = plan

        super().__init__(
            name=plan.name,
            description=plan.description,
            mission_id=plan.mission_id,
        )

    def build_steps(self) -> None:
        """Convert plan steps into executable workflow steps."""

        workflow_step_ids: dict[UUID, UUID] = {}

        for plan_step in self.plan.steps:
            resolved_dependencies = [
                workflow_step_ids[dependency_id]
                for dependency_id
                in plan_step.dependency_plan_step_ids
            ]

            workflow_step = self.add_step(
                name=plan_step.name,
                description=plan_step.description,
                department=plan_step.department,
                dependency_step_ids=resolved_dependencies,
                requires_approval=(
                    plan_step.requires_approval
                ),
                maximum_retries=(
                    plan_step.maximum_retries
                ),
                input_data={
                    "mission_id": str(self.plan.mission_id),
                    "plan_id": str(self.plan.plan_id),
                },
            )

            workflow_step_ids[
                plan_step.plan_step_id
            ] = workflow_step.step_id


class WorkflowPlanner:
    """
    Creates operational plans and executable workflows for the COO.
    """

    def __init__(self) -> None:
        self.logger = get_logger(
            "operations.workflow_planner"
        )

    def create_plan(
        self,
        mission: MissionRecord,
    ) -> WorkflowPlan:
        """
        Create a generic operational plan for an approved mission.

        Raises:
            ValidationError:
                If the mission is not ready for workflow planning.
        """

        if mission.is_terminal:
            raise ValidationError(
                "A terminal mission cannot be planned.",
                details={
                    "mission_id": str(mission.mission_id),
                    "status": mission.status.value,
                },
            )

        if not mission.is_approved:
            raise ValidationError(
                "The mission must be approved before workflow planning.",
                details={
                    "mission_id": str(mission.mission_id),
                    "approval_status": (
                        mission.approval_status.value
                    ),
                },
            )

        if mission.lead_department is None:
            raise ValidationError(
                "A mission requires a lead department before planning.",
                details={
                    "mission_id": str(mission.mission_id),
                },
            )

        if not mission.objectives:
            raise ValidationError(
                "A mission requires measurable objectives "
                "before workflow planning.",
                details={
                    "mission_id": str(mission.mission_id),
                },
            )

        planning_step = WorkflowPlanStep(
            name="Prepare mission execution plan",
            description=(
                "Review mission objectives, constraints, resources, "
                "dependencies, and expected outputs."
            ),
            department=mission.lead_department,
        )

        execution_step = WorkflowPlanStep(
            name="Execute mission objectives",
            description=(
                "Coordinate the responsible department and complete "
                "the approved mission objectives."
            ),
            department=mission.lead_department,
            dependency_plan_step_ids=[
                planning_step.plan_step_id
            ],
        )

        review_step = WorkflowPlanStep(
            name="Review mission results",
            description=(
                "Verify outputs against mission success criteria and "
                "submit the result for executive review."
            ),
            department=DepartmentName.EXECUTIVE,
            dependency_plan_step_ids=[
                execution_step.plan_step_id
            ],
            requires_approval=True,
        )

        plan = WorkflowPlan(
            mission_id=mission.mission_id,
            name=f"Operations plan: {mission.title}",
            description=(
                "Generic COO workflow generated from the approved "
                "company mission."
            ),
            lead_department=mission.lead_department,
            steps=[
                planning_step,
                execution_step,
                review_step,
            ],
        )

        self.logger.info(
            "Workflow plan created: %s | mission_id=%s | steps=%s",
            plan.name,
            mission.mission_id,
            len(plan.steps),
        )

        return plan

    def create_workflow(
        self,
        mission: MissionRecord,
    ) -> PlannedWorkflow:
        """Create an executable workflow from an approved mission."""

        plan = self.create_plan(mission)
        workflow = PlannedWorkflow(plan=plan)

        self.logger.info(
            "Executable workflow created: %s | workflow_id=%s",
            workflow.name,
            workflow.workflow_id,
        )

        return workflow


workflow_planner = WorkflowPlanner()