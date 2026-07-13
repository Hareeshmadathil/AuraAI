"""Creative Quality Director and typed review planning."""

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
    ValidationError,
    utc_now,
)
from creative_quality.models import CreativeQualityStage
from creative_quality.task_inputs import require_model
from production.models import ProductionPackage, ProductionStage


class CreativeQualityReviewAssignment(AuraBaseModel):
    """One dependency-ordered quality review responsibility."""

    assignment_id: UUID = Field(default_factory=uuid4)
    sequence_number: int = Field(ge=1)
    stage: CreativeQualityStage
    specialist_role: str = Field(min_length=1, max_length=150)
    expected_output: str = Field(min_length=1, max_length=250)
    depends_on: list[UUID] = Field(default_factory=list)
    founder_review: bool = False


class CreativeQualityReviewPlan(AuraBaseModel):
    """Director plan that grants no quality or render approval."""

    plan_id: UUID = Field(default_factory=uuid4)
    production_package_id: UUID
    assignments: list[CreativeQualityReviewAssignment] = Field(min_length=1)
    founder_review_required: bool = True
    created_by_agent_id: UUID
    created_by_name: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_order(self) -> "CreativeQualityReviewPlan":
        known: set[UUID] = set()
        for expected, assignment in enumerate(self.assignments, start=1):
            if assignment.sequence_number != expected:
                raise ValueError("Quality assignments must be sequential.")
            if not set(assignment.depends_on).issubset(known):
                raise ValueError("Quality dependencies must reference earlier work.")
            known.add(assignment.assignment_id)
        return self

    def to_task_records(self) -> list[TaskRecord]:
        """Project assignments into Creative Quality tasks."""

        return [
            TaskRecord(
                title=f"Creative Quality: {item.stage.value.replace('_', ' ')}",
                description=(
                    f"{item.specialist_role} prepares {item.expected_output} "
                    "using deterministic offline review."
                ),
                department=DepartmentName.CREATIVE_QUALITY,
                priority=(
                    TaskPriority.CRITICAL
                    if item.stage == CreativeQualityStage.FACTUALITY_REVIEW
                    else TaskPriority.HIGH
                ),
                input_data={
                    "quality_plan_id": str(self.plan_id),
                    "production_package_id": str(self.production_package_id),
                    "stage": item.stage.value,
                    "specialist_role": item.specialist_role,
                    "expected_output": item.expected_output,
                    "founder_review": item.founder_review,
                    "dependency_assignment_ids": [
                        str(value) for value in item.depends_on
                    ],
                },
            )
            for item in self.assignments
        ]


class CreativeDirector(BaseEmployee):
    """Coordinate reviews without performing analysis or approval."""

    def __init__(self) -> None:
        super().__init__(
            name="Muse",
            job_title="Creative Quality Director",
            department=DepartmentName.CREATIVE_QUALITY,
            description=(
                "Coordinates quality review and revision planning without "
                "performing specialist analysis or granting approval."
            ),
        )

    def perform_task(self, task: TaskRecord) -> OperationResult:
        package = require_model(
            task.input_data, "production_package", ProductionPackage
        )
        self._validate_package(package)
        plan = self.create_review_plan(package)
        tasks = plan.to_task_records()
        return OperationResult.ok(
            "Creative Director created the quality review plan.",
            data={
                "review_plan": plan.model_dump(mode="json"),
                "generated_tasks": [item.model_dump(mode="json") for item in tasks],
            },
        )

    def create_review_plan(
        self, package: ProductionPackage
    ) -> CreativeQualityReviewPlan:
        """Create the dependency-ordered review sequence."""

        definitions = (
            (CreativeQualityStage.HOOK_REVIEW, "Hook Architect", "HookAnalysis"),
            (CreativeQualityStage.STORY_REVIEW, "Story Director", "StoryFlowReport"),
            (
                CreativeQualityStage.RETENTION_REVIEW,
                "Retention Auditor",
                "RetentionReport",
            ),
            (CreativeQualityStage.MOTION_REVIEW, "Motion Designer", "MotionPlan"),
            (
                CreativeQualityStage.SUBTITLE_REVIEW,
                "Subtitle Designer",
                "SubtitleOptimization",
            ),
            (
                CreativeQualityStage.THUMBNAIL_REVIEW,
                "Thumbnail Psychologist",
                "ThumbnailQualityReport",
            ),
            (
                CreativeQualityStage.FACTUALITY_REVIEW,
                "Factuality Reviewer",
                "FactualityReport",
            ),
            (
                CreativeQualityStage.SCORING,
                "Creative Quality System",
                "CreativeQualityScores",
            ),
            (CreativeQualityStage.REVISION, "Creative Quality System", "RevisionPlan"),
            (CreativeQualityStage.APPROVAL, "Founder", "Founder quality decision"),
        )
        assignments: list[CreativeQualityReviewAssignment] = []
        for sequence, (stage, role, output) in enumerate(definitions, start=1):
            assignments.append(
                CreativeQualityReviewAssignment(
                    sequence_number=sequence,
                    stage=stage,
                    specialist_role=role,
                    expected_output=output,
                    depends_on=(
                        [] if not assignments else [assignments[-1].assignment_id]
                    ),
                    founder_review=stage == CreativeQualityStage.APPROVAL,
                )
            )
        return CreativeQualityReviewPlan(
            production_package_id=package.package_id,
            assignments=assignments,
            created_by_agent_id=self.agent_id,
            created_by_name=self.name,
        )

    @staticmethod
    def _validate_package(package: ProductionPackage) -> None:
        if package.current_stage not in {
            ProductionStage.APPROVAL,
            ProductionStage.COMPLETED,
        }:
            raise ValidationError(
                "Creative Quality requires a completed or review-ready package."
            )
        if package.quality_report is None:
            raise ValidationError(
                "Creative Quality requires the Production quality report."
            )
