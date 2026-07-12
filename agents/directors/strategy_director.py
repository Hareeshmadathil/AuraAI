"""
Strategy Director for AuraAI Creator OS.

The Strategy Director converts an approved company mission into a
structured strategic work plan. The director does not perform detailed
market research personally. Instead, the director defines the work that
must be completed by research, audience, monetization, and branding
specialists.
"""

from __future__ import annotations

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


class StrategyWorkItem(AuraBaseModel):
    """One strategic work item assigned to a department."""

    work_item_id: UUID = Field(default_factory=uuid4)

    title: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str = Field(
        min_length=1,
        max_length=5000,
    )

    department: DepartmentName

    priority: TaskPriority = TaskPriority.NORMAL

    expected_output: str = Field(
        min_length=1,
        max_length=2000,
    )

    dependency_work_item_ids: list[UUID] = Field(
        default_factory=list
    )

    requires_user_approval: bool = False


class StrategyPlan(AuraBaseModel):
    """Structured strategy plan created for one company mission."""

    strategy_plan_id: UUID = Field(default_factory=uuid4)

    mission_id: UUID

    mission_title: str = Field(
        min_length=1,
        max_length=250,
    )

    strategic_goal: str = Field(
        min_length=1,
        max_length=5000,
    )

    work_items: list[StrategyWorkItem] = Field(
        min_length=1,
    )

    final_deliverable: str = Field(
        min_length=1,
        max_length=5000,
    )

    created_by_agent_id: UUID

    created_by_name: str = Field(
        min_length=1,
        max_length=150,
    )

    created_at: Any = Field(default_factory=utc_now)

    @property
    def work_item_count(self) -> int:
        """Return the number of planned strategic work items."""

        return len(self.work_items)

    def to_task_records(self) -> list[TaskRecord]:
        """
        Convert planned work items into employee task records.

        Dependencies remain represented in the plan. Workflow-level
        dependency execution will be connected in a later milestone.
        """

        return [
            TaskRecord(
                title=work_item.title,
                description=work_item.description,
                department=work_item.department,
                priority=work_item.priority,
                input_data={
                    "strategy_plan_id": str(
                        self.strategy_plan_id
                    ),
                    "mission_id": str(self.mission_id),
                    "expected_output": (
                        work_item.expected_output
                    ),
                    "dependency_work_item_ids": [
                        str(dependency_id)
                        for dependency_id
                        in work_item.dependency_work_item_ids
                    ],
                    "requires_user_approval": (
                        work_item.requires_user_approval
                    ),
                },
            )
            for work_item in self.work_items
        ]


class StrategyDirector(BaseEmployee):
    """
    Director responsible for AuraAI's strategic planning.

    Responsibilities:

    - translate approved missions into strategic plans;
    - define research and analysis requirements;
    - assign work to the appropriate departments;
    - ensure monetization and production feasibility are considered;
    - prepare a final recommendation for Aura CEO and the user.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Nova",
            job_title="Strategy Director",
            department=DepartmentName.STRATEGY,
            description=(
                "Transforms approved company missions into strategic "
                "plans covering niche, audience, positioning, brand, "
                "monetization, and launch requirements."
            ),
        )

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        """
        Create a strategy plan from a supplied mission.

        Expected task input:

        ``task.input_data["mission"]``
        """

        mission = self._require_mission(
            task.input_data
        )

        plan = self.create_strategy_plan(mission)
        tasks = plan.to_task_records()

        return OperationResult.ok(
            "Strategy Director created the mission strategy plan.",
            data={
                "mission_id": str(mission.mission_id),
                "strategy_plan": plan.model_dump(mode="json"),
                "generated_tasks": [
                    generated_task.model_dump(mode="json")
                    for generated_task in tasks
                ],
            },
        )

    def create_strategy_plan(
        self,
        mission: MissionRecord,
    ) -> StrategyPlan:
        """
        Create the strategic work plan for an approved mission.

        Raises:
            ValidationError:
                If the mission is not ready for strategic planning.
        """

        if mission.is_terminal:
            raise ValidationError(
                "A terminal mission cannot receive a strategy plan.",
                details={
                    "mission_id": str(mission.mission_id),
                    "status": mission.status.value,
                },
            )

        if not mission.is_approved:
            raise ValidationError(
                "The mission must be approved before strategy planning.",
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
                "strategy planning.",
                details={
                    "mission_id": str(mission.mission_id),
                },
            )

        niche_research = StrategyWorkItem(
            title="Research profitable content niches",
            description=(
                "Identify sustainable niches with audience demand, "
                "manageable competition, production feasibility, and "
                "multiple monetization paths."
            ),
            department=DepartmentName.RESEARCH,
            priority=TaskPriority.HIGH,
            expected_output=(
                "A ranked shortlist of validated niche opportunities "
                "with evidence and risk analysis."
            ),
        )

        audience_analysis = StrategyWorkItem(
            title="Define the target audience",
            description=(
                "Analyze the needs, motivations, locations, content "
                "preferences, and purchasing intent of the likely "
                "audience for the shortlisted niches."
            ),
            department=DepartmentName.RESEARCH,
            priority=TaskPriority.HIGH,
            expected_output=(
                "A complete primary viewer profile and secondary "
                "audience profile."
            ),
            dependency_work_item_ids=[
                niche_research.work_item_id
            ],
        )

        monetization_analysis = StrategyWorkItem(
            title="Map realistic monetization options",
            description=(
                "Evaluate advertising, affiliate, sponsorship, digital "
                "product, service, and lead-generation opportunities "
                "without assuming platform monetization is guaranteed."
            ),
            department=DepartmentName.REVENUE,
            priority=TaskPriority.HIGH,
            expected_output=(
                "A revenue map with free-first recommendations, "
                "eligibility requirements, risks, and expected order "
                "of implementation."
            ),
            dependency_work_item_ids=[
                niche_research.work_item_id,
                audience_analysis.work_item_id,
            ],
        )

        brand_positioning = StrategyWorkItem(
            title="Develop brand positioning and name candidates",
            description=(
                "Create a clear brand promise, differentiation, tone, "
                "naming criteria, and an initial shortlist of original "
                "brand-name candidates."
            ),
            department=DepartmentName.STRATEGY,
            priority=TaskPriority.HIGH,
            expected_output=(
                "A positioning statement, brand personality, naming "
                "criteria, and ranked brand-name shortlist."
            ),
            dependency_work_item_ids=[
                niche_research.work_item_id,
                audience_analysis.work_item_id,
            ],
        )

        platform_plan = StrategyWorkItem(
            title="Prepare the social-platform launch plan",
            description=(
                "Define the roles of YouTube, YouTube Shorts, "
                "Instagram, and TikTok, including content formats, "
                "account requirements, posting priorities, and "
                "monetization limitations."
            ),
            department=DepartmentName.DISTRIBUTION,
            priority=TaskPriority.NORMAL,
            expected_output=(
                "A platform-by-platform launch plan ready for account "
                "creation after final brand approval."
            ),
            dependency_work_item_ids=[
                audience_analysis.work_item_id,
                brand_positioning.work_item_id,
            ],
        )

        final_review = StrategyWorkItem(
            title="Submit the complete launch strategy for approval",
            description=(
                "Combine research, audience, monetization, branding, "
                "and platform findings into one recommendation for "
                "Aura CEO and the user."
            ),
            department=DepartmentName.EXECUTIVE,
            priority=TaskPriority.HIGH,
            expected_output=(
                "One complete strategy recommendation with a chosen "
                "niche, positioning, brand shortlist, monetization "
                "roadmap, and social launch plan."
            ),
            dependency_work_item_ids=[
                monetization_analysis.work_item_id,
                brand_positioning.work_item_id,
                platform_plan.work_item_id,
            ],
            requires_user_approval=True,
        )

        return StrategyPlan(
            mission_id=mission.mission_id,
            mission_title=mission.title,
            strategic_goal=(
                "Select and prepare AuraAI's first sustainable creator "
                "business opportunity before creating public accounts."
            ),
            work_items=[
                niche_research,
                audience_analysis,
                monetization_analysis,
                brand_positioning,
                platform_plan,
                final_review,
            ],
            final_deliverable=(
                "An evidence-based company launch package containing "
                "the approved niche, audience, brand positioning, "
                "brand-name shortlist, monetization roadmap, and "
                "platform launch plan."
            ),
            created_by_agent_id=self.agent_id,
            created_by_name=self.name,
        )

    @staticmethod
    def _require_mission(
        input_data: dict[str, Any],
    ) -> MissionRecord:
        """Extract and validate the mission supplied to the director."""

        mission_value = input_data.get("mission")

        if mission_value is None:
            raise ValidationError(
                "Strategy Director requires a mission in "
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
                    "The supplied strategy mission is invalid.",
                    details={
                        "exception_type": (
                            error.__class__.__name__
                        ),
                    },
                ) from error

        raise ValidationError(
            "Strategy mission input must be a MissionRecord "
            "or dictionary.",
            details={
                "received_type": (
                    mission_value.__class__.__name__
                ),
            },
        )