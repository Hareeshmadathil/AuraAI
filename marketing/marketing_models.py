"""Structured models for AuraAI Marketing Department plans."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import (
    AuraBaseModel,
    ContentPlatform,
    DepartmentName,
    TaskPriority,
    TaskRecord,
    utc_now,
)


class MarketingObjective(AuraBaseModel):
    """One measurable campaign objective in a marketing plan."""

    objective_id: UUID = Field(default_factory=uuid4)
    description: str = Field(min_length=1, max_length=1000)
    success_metric: str = Field(min_length=1, max_length=500)
    target_value: str = Field(min_length=1, max_length=250)
    priority: TaskPriority = TaskPriority.NORMAL


class PlatformAssignment(AuraBaseModel):
    """The campaign role and deliverables for one content platform."""

    assignment_id: UUID = Field(default_factory=uuid4)
    platform: ContentPlatform
    platform_role: str = Field(min_length=1, max_length=1000)
    content_formats: list[str] = Field(min_length=1)
    campaign_goal: str = Field(min_length=1, max_length=1000)
    expected_outputs: list[str] = Field(min_length=1)
    priority: TaskPriority = TaskPriority.NORMAL
    requires_final_approval: bool = True


class MarketingPlan(AuraBaseModel):
    """Complete cross-platform marketing plan for an approved mission."""

    marketing_plan_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    mission_title: str = Field(min_length=1, max_length=250)
    brand_positioning: str = Field(min_length=1, max_length=3000)
    content_pillars: list[str] = Field(min_length=1)
    audience_promise: str = Field(min_length=1, max_length=2000)
    campaign_goals: list[MarketingObjective] = Field(min_length=1)
    platform_assignments: list[PlatformAssignment] = Field(min_length=1)
    expected_outputs: list[str] = Field(min_length=1)
    final_approval_required: bool = True
    created_by_agent_id: UUID
    created_by_name: str = Field(min_length=1, max_length=150)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_platforms_and_approval(self) -> "MarketingPlan":
        """Require unique platforms and approval before execution."""

        platforms = [
            assignment.platform
            for assignment in self.platform_assignments
        ]

        if len(platforms) != len(set(platforms)):
            raise ValueError(
                "Marketing platform assignments must be unique."
            )

        if not self.final_approval_required:
            raise ValueError(
                "Marketing plans require final approval."
            )

        return self

    @property
    def assignment_count(self) -> int:
        """Return the number of platform assignments."""

        return len(self.platform_assignments)

    def to_task_records(self) -> list[TaskRecord]:
        """Convert platform assignments into AuraAI task records."""

        return [
            TaskRecord(
                title=f"Prepare {assignment.platform.value} campaign",
                description=assignment.platform_role,
                department=DepartmentName.MARKETING,
                priority=assignment.priority,
                input_data={
                    "marketing_plan_id": str(self.marketing_plan_id),
                    "mission_id": str(self.mission_id),
                    "platform": assignment.platform.value,
                    "content_formats": list(
                        assignment.content_formats
                    ),
                    "campaign_goal": assignment.campaign_goal,
                    "expected_outputs": list(
                        assignment.expected_outputs
                    ),
                    "requires_final_approval": (
                        assignment.requires_final_approval
                    ),
                },
            )
            for assignment in self.platform_assignments
        ]
