"""
Research Director for AuraAI Creator OS.

The Research Director translates an approved company mission into a
structured research plan. The director coordinates research employees
but does not personally perform detailed trend, audience, competitor,
or monetization analysis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from agents.base_employee import BaseEmployee
from core import (
    AuraBaseModel,
    DepartmentName,
    MissionRecord,
    OperationResult,
    TaskPriority,
    TaskRecord,
    ValidationError,
    utc_now,
)


class ResearchAssignment(AuraBaseModel):
    """One specialist assignment inside a research plan."""

    assignment_id: UUID = Field(default_factory=uuid4)

    title: str = Field(
        min_length=1,
        max_length=250,
    )

    specialist_role: str = Field(
        min_length=1,
        max_length=150,
    )

    description: str = Field(
        min_length=1,
        max_length=5000,
    )

    research_questions: list[str] = Field(
        min_length=1,
    )

    expected_output: str = Field(
        min_length=1,
        max_length=3000,
    )

    priority: TaskPriority = TaskPriority.NORMAL

    dependency_assignment_ids: list[UUID] = Field(
        default_factory=list,
    )


class ResearchPlan(AuraBaseModel):
    """Complete research plan created for one mission."""

    research_plan_id: UUID = Field(default_factory=uuid4)

    mission_id: UUID

    mission_title: str = Field(
        min_length=1,
        max_length=250,
    )

    research_goal: str = Field(
        min_length=1,
        max_length=5000,
    )

    assignments: list[ResearchAssignment] = Field(
        min_length=1,
    )

    synthesis_requirements: list[str] = Field(
        min_length=1,
    )

    created_by_agent_id: UUID

    created_by_name: str = Field(
        min_length=1,
        max_length=150,
    )

    created_at: datetime = Field(default_factory=utc_now)

    @property
    def assignment_count(self) -> int:
        """Return the number of specialist assignments."""

        return len(self.assignments)

    def to_task_records(self) -> list[TaskRecord]:
        """Convert specialist assignments into AuraAI tasks."""

        return [
            TaskRecord(
                title=assignment.title,
                description=assignment.description,
                department=DepartmentName.RESEARCH,
                priority=assignment.priority,
                input_data={
                    "research_plan_id": str(
                        self.research_plan_id
                    ),
                    "mission_id": str(self.mission_id),
                    "specialist_role": (
                        assignment.specialist_role
                    ),
                    "research_questions": list(
                        assignment.research_questions
                    ),
                    "expected_output": (
                        assignment.expected_output
                    ),
                    "dependency_assignment_ids": [
                        str(dependency_id)
                        for dependency_id
                        in assignment.dependency_assignment_ids
                    ],
                },
            )
            for assignment in self.assignments
        ]


class ResearchDirector(BaseEmployee):
    """
    Director responsible for coordinating AuraAI research operations.

    Responsibilities:

    - define research scope;
    - divide work among research specialists;
    - establish dependencies and expected outputs;
    - ensure findings are evidence-based;
    - prepare requirements for the final research synthesis.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Atlas",
            job_title="Research Director",
            department=DepartmentName.RESEARCH,
            description=(
                "Coordinates trend, competitor, audience, and market "
                "research and ensures that strategic recommendations "
                "are supported by reliable evidence."
            ),
        )

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        """Create a research plan from an approved mission."""

        mission = self._require_mission(
            task.input_data
        )

        plan = self.create_research_plan(mission)
        generated_tasks = plan.to_task_records()

        return OperationResult.ok(
            "Research Director created the mission research plan.",
            data={
                "mission_id": str(mission.mission_id),
                "research_plan": plan.model_dump(mode="json"),
                "generated_tasks": [
                    generated_task.model_dump(mode="json")
                    for generated_task in generated_tasks
                ],
            },
        )

    def create_research_plan(
        self,
        mission: MissionRecord,
    ) -> ResearchPlan:
        """Create a structured specialist research plan."""

        if mission.is_terminal:
            raise ValidationError(
                "A terminal mission cannot receive a research plan.",
                details={
                    "mission_id": str(mission.mission_id),
                    "status": mission.status.value,
                },
            )

        if not mission.is_approved:
            raise ValidationError(
                "The mission must be approved before research planning.",
                details={
                    "mission_id": str(mission.mission_id),
                    "approval_status": (
                        mission.approval_status.value
                    ),
                },
            )

        if not mission.objectives:
            raise ValidationError(
                "The mission requires measurable objectives before "
                "research planning.",
                details={
                    "mission_id": str(mission.mission_id),
                },
            )

        trend_assignment = ResearchAssignment(
            title="Discover and score emerging content opportunities",
            specialist_role="Trend Hunter",
            description=(
                "Identify topics and niches showing meaningful audience "
                "demand, momentum, monetization potential, and practical "
                "production feasibility."
            ),
            research_questions=[
                "Which topics are gaining measurable attention?",
                "Is the demand temporary, seasonal, or evergreen?",
                "How competitive is each opportunity?",
                "Can AuraAI produce original content consistently?",
                "What realistic revenue paths exist?",
            ],
            expected_output=(
                "A ranked opportunity report containing scores, "
                "evidence, risks, and recommended next steps."
            ),
            priority=TaskPriority.HIGH,
        )

        competitor_assignment = ResearchAssignment(
            title="Analyze competitors and content gaps",
            specialist_role="Research Analyst",
            description=(
                "Study relevant creators, formats, publishing patterns, "
                "viewer responses, and unmet audience needs without "
                "copying protected content."
            ),
            research_questions=[
                "Which creators currently lead each shortlisted niche?",
                "Which formats and topics repeatedly perform well?",
                "What important audience questions remain unanswered?",
                "Where can AuraAI provide meaningfully better value?",
            ],
            expected_output=(
                "A competitor landscape and content-gap report with "
                "original differentiation opportunities."
            ),
            priority=TaskPriority.HIGH,
            dependency_assignment_ids=[
                trend_assignment.assignment_id
            ],
        )

        audience_assignment = ResearchAssignment(
            title="Build the primary viewer profile",
            specialist_role="Audience Analyst",
            description=(
                "Define the target viewer's goals, frustrations, "
                "locations, preferred platforms, content habits, and "
                "commercial intent."
            ),
            research_questions=[
                "Who has the strongest need for this content?",
                "What problems are they actively trying to solve?",
                "Which content formats do they prefer?",
                "What would make them subscribe or return?",
                "Which products or services are relevant to them?",
            ],
            expected_output=(
                "A primary viewer profile, secondary audience profile, "
                "viewer problems, and content expectations."
            ),
            priority=TaskPriority.HIGH,
            dependency_assignment_ids=[
                trend_assignment.assignment_id,
                competitor_assignment.assignment_id,
            ],
        )

        return ResearchPlan(
            mission_id=mission.mission_id,
            mission_title=mission.title,
            research_goal=(
                "Produce reliable evidence for selecting AuraAI's first "
                "sustainable niche, audience, positioning, and content "
                "opportunity."
            ),
            assignments=[
                trend_assignment,
                competitor_assignment,
                audience_assignment,
            ],
            synthesis_requirements=[
                "Separate verified findings from assumptions.",
                "Record evidence sources for important claims.",
                "Explain risks and limitations.",
                "Do not guarantee views, revenue, or monetization.",
                "Prioritize original and sustainable content.",
                "Recommend one primary option and at least one fallback.",
            ],
            created_by_agent_id=self.agent_id,
            created_by_name=self.name,
        )

    @staticmethod
    def _require_mission(
        input_data: dict[str, Any],
    ) -> MissionRecord:
        """Extract and validate a mission from task input."""

        mission_value = input_data.get("mission")

        if mission_value is None:
            raise ValidationError(
                "Research Director requires a mission in "
                "task.input_data.",
                details={
                    "required_key": "mission",
                },
            )

        if isinstance(mission_value, MissionRecord):
            return mission_value

        if isinstance(mission_value, dict):
            try:
                return MissionRecord.model_validate(
                    mission_value
                )
            except Exception as error:
                raise ValidationError(
                    "The supplied research mission is invalid.",
                    details={
                        "exception_type": (
                            error.__class__.__name__
                        ),
                    },
                ) from error

        raise ValidationError(
            "Research mission input must be a MissionRecord "
            "or dictionary.",
            details={
                "received_type": (
                    mission_value.__class__.__name__
                ),
            },
        )