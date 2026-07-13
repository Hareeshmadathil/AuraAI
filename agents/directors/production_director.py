"""Production Director for deterministic, review-ready content planning."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from agents.base_employee import BaseEmployee
from core import (
    AuraBaseModel,
    DepartmentName,
    OperationResult,
    TaskPriority,
    TaskRecord,
    utc_now,
)
from production.content_brief import ContentBriefBuilder
from production.models import ApprovalRequirement, ProductionInput, ProductionStage
from production.task_inputs import require_model


class ProductionAssignment(AuraBaseModel):
    """One ordered production responsibility assigned to a specialist."""

    assignment_id: UUID = Field(default_factory=uuid4)
    sequence_number: int = Field(ge=1)
    stage: ProductionStage
    specialist_role: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1, max_length=3000)
    expected_output: str = Field(min_length=1, max_length=1000)
    dependency_assignment_ids: list[UUID] = Field(default_factory=list)
    priority: TaskPriority = TaskPriority.HIGH
    approval_requirement: ApprovalRequirement = ApprovalRequirement.NONE


class ProductionPlan(AuraBaseModel):
    """Director-owned ordered work plan for one production input."""

    plan_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID | None = None
    brief_id: UUID
    assignments: list[ProductionAssignment] = Field(min_length=1)
    final_approval_requirement: ApprovalRequirement
    created_by_agent_id: UUID
    created_by_name: str = Field(min_length=1, max_length=150)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_order(self) -> "ProductionPlan":
        expected = list(range(1, len(self.assignments) + 1))
        if [item.sequence_number for item in self.assignments] != expected:
            raise ValueError("Production assignments must be sequential.")
        known: set[UUID] = set()
        for item in self.assignments:
            if not set(item.dependency_assignment_ids).issubset(known):
                raise ValueError("Production dependencies must refer to earlier work.")
            known.add(item.assignment_id)
        return self

    def to_task_records(self) -> list[TaskRecord]:
        """Convert assignments into department-owned task records."""

        return [
            TaskRecord(
                title=item.title,
                description=item.description,
                department=DepartmentName.PRODUCTION,
                priority=item.priority,
                input_data={
                    "production_plan_id": str(self.plan_id),
                    "brief_id": str(self.brief_id),
                    "stage": item.stage.value,
                    "specialist_role": item.specialist_role,
                    "expected_output": item.expected_output,
                    "dependency_assignment_ids": [
                        str(identifier) for identifier in item.dependency_assignment_ids
                    ],
                    "approval_requirement": item.approval_requirement.value,
                },
            )
            for item in self.assignments
        ]


class ProductionDirector(BaseEmployee):
    """Coordinate production stages without authoring or editing media."""

    def __init__(self, brief_builder: ContentBriefBuilder | None = None) -> None:
        super().__init__(
            name="Vega",
            job_title="Production Director",
            department=DepartmentName.PRODUCTION,
            description=(
                "Creates content briefs and assigns ordered production work; "
                "does not write scripts, generate assets, or edit media."
            ),
        )
        self.brief_builder = brief_builder or ContentBriefBuilder()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Create the brief, plan, and specialist task projections."""

        production_input = require_model(
            task.input_data, "production_input", ProductionInput
        )
        brief = self.brief_builder.build(production_input)
        plan = self.create_production_plan(production_input, brief.brief_id)
        tasks = plan.to_task_records()
        return OperationResult.ok(
            "Production Director created the ordered production plan.",
            data={
                "content_brief": brief.model_dump(mode="json"),
                "production_plan": plan.model_dump(mode="json"),
                "generated_tasks": [item.model_dump(mode="json") for item in tasks],
            },
        )

    def create_production_plan(
        self,
        production_input: ProductionInput,
        brief_id: UUID,
    ) -> ProductionPlan:
        """Create seven dependency-ordered specialist assignments."""

        roles = (
            (ProductionStage.SCRIPT, "Script Writer", "Write the deterministic script", "VideoScript"),
            (ProductionStage.STORYBOARD, "Storyboard Artist", "Create storyboard and visual direction", "Storyboard"),
            (ProductionStage.VOICE, "Voice Artist", "Plan the voice performance", "VoiceoverPlan"),
            (ProductionStage.THUMBNAIL, "Thumbnail Designer", "Develop truthful thumbnail concepts", "ThumbnailPlan"),
            (ProductionStage.SHORT_FORM, "Shorts Editor", "Adapt short-form derivatives", "ShortFormPackage"),
            (ProductionStage.ASSEMBLY, "Video Editor", "Create the non-rendered assembly manifest", "VideoAssemblyManifest"),
            (ProductionStage.QUALITY_CONTROL, "Production Quality Controller", "Review quality, safety, and governance", "ProductionQualityReport"),
        )
        assignments: list[ProductionAssignment] = []
        for sequence, (stage, role, title, output) in enumerate(roles, start=1):
            dependencies = (
                [] if sequence == 1 else [assignments[-1].assignment_id]
            )
            approval = (
                ApprovalRequirement.FOUNDER_REQUIRED
                if stage == ProductionStage.QUALITY_CONTROL
                and production_input.requires_founder_approval
                else ApprovalRequirement.NONE
            )
            assignments.append(
                ProductionAssignment(
                    sequence_number=sequence,
                    stage=stage,
                    specialist_role=role,
                    title=title,
                    description=(
                        f"{role} prepares {output} from approved upstream production "
                        "inputs without calling external providers."
                    ),
                    expected_output=output,
                    dependency_assignment_ids=dependencies,
                    approval_requirement=approval,
                )
            )
        return ProductionPlan(
            mission_id=production_input.mission_id,
            brief_id=brief_id,
            assignments=assignments,
            final_approval_requirement=(
                ApprovalRequirement.FOUNDER_REQUIRED
                if production_input.requires_founder_approval
                else ApprovalRequirement.AUTOMATED_SAFE
            ),
            created_by_agent_id=self.agent_id,
            created_by_name=self.name,
        )
