"""
Aura CEO employee for AuraAI Creator OS.

Aura is the chief executive officer and strategic brain of the company.
She reviews high-level missions, checks whether they are ready to
proceed, creates structured executive decisions, and assigns appropriate
follow-up actions.

This first version is deterministic. AI-provider reasoning will be added
only after the executive rules and tests are stable.
"""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from core import (
    DecisionOutcome,
    DecisionRecord,
    DecisionType,
    DepartmentName,
    MissionRecord,
    MissionStatus,
    OperationResult,
    TaskRecord,
    ValidationError,
)


class AuraCEO(BaseEmployee):
    """
    Chief executive officer of AuraAI Creator OS.

    Aura does not perform specialist work such as research, scripting,
    editing, or publishing. She evaluates missions, records decisions,
    and delegates follow-up work to the correct departments.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Aura",
            job_title="Chief Executive Officer",
            department=DepartmentName.EXECUTIVE,
            description=(
                "Leads AuraAI, reviews company missions, makes "
                "executive decisions, protects company principles, "
                "and delegates work to departments."
            ),
        )

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        """
        Review a mission supplied through a task.

        Expected input:

        ``task.input_data["mission"]``

        The mission may be a ``MissionRecord`` instance or a dictionary
        that can be validated into one.
        """

        mission_value = task.input_data.get("mission")

        if mission_value is None:
            raise ValidationError(
                "Aura CEO requires a mission in task.input_data.",
                details={
                    "required_key": "mission",
                    "task_id": str(task.task_id),
                },
            )

        mission = self._parse_mission(mission_value)
        decision = self.review_mission(mission)

        return OperationResult.ok(
            "Aura completed the executive mission review.",
            data={
                "mission_id": str(mission.mission_id),
                "decision": decision.model_dump(mode="json"),
            },
        )

    def review_mission(
        self,
        mission: MissionRecord,
    ) -> DecisionRecord:
        """
        Review one company mission and create an executive decision.

        Decision rules in this version:

        - terminal missions are rejected;
        - missions without measurable objectives require more research;
        - missions without a lead department require user input;
        - properly defined missions are approved.
        """

        decision = DecisionRecord(
            title=f"Executive review: {mission.title}",
            decision_type=DecisionType.STRATEGIC,
            decision_maker_agent_id=self.agent_id,
            decision_maker_name=self.name,
            mission_id=mission.mission_id,
            department=DepartmentName.EXECUTIVE,
            requires_user_confirmation=(
                mission.requires_user_approval
            ),
            context={
                "mission_status": mission.status.value,
                "mission_priority": mission.priority.value,
                "requested_by": mission.requested_by,
                "objective_count": len(mission.objectives),
                "lead_department": (
                    mission.lead_department.value
                    if mission.lead_department is not None
                    else None
                ),
            },
        )

        decision.add_evidence(
            title="Mission definition",
            description=(
                "Aura reviewed the mission title, description, "
                "objectives, approval requirements, ownership, "
                "priority, and current lifecycle status."
            ),
            source_type="mission_record",
            source_reference=str(mission.mission_id),
            reliability_score=1.0,
            metadata={
                "status": mission.status.value,
                "objectives": len(mission.objectives),
            },
        )

        if mission.is_terminal:
            self._reject_terminal_mission(
                mission=mission,
                decision=decision,
            )
            return decision

        if not mission.objectives:
            self._request_objective_research(
                mission=mission,
                decision=decision,
            )
            return decision

        if mission.lead_department is None:
            self._request_department_selection(
                mission=mission,
                decision=decision,
            )
            return decision

        self._approve_ready_mission(
            mission=mission,
            decision=decision,
        )

        return decision

    def _reject_terminal_mission(
        self,
        *,
        mission: MissionRecord,
        decision: DecisionRecord,
    ) -> None:
        """Reject a mission that has already reached a final state."""

        decision.add_next_action(
            description=(
                "Create a new mission if additional work is required."
            ),
            department=DepartmentName.EXECUTIVE,
        )

        decision.decide(
            outcome=DecisionOutcome.REJECTED,
            reasoning=(
                f"The mission is already in the terminal state "
                f"'{mission.status.value}' and cannot be executed "
                "again. A separate mission must be created for any "
                "new objective."
            ),
            confidence_score=1.0,
        )

    def _request_objective_research(
        self,
        *,
        mission: MissionRecord,
        decision: DecisionRecord,
    ) -> None:
        """Request measurable objectives before approving a mission."""

        decision.add_next_action(
            description=(
                "Research the mission and define measurable objectives "
                "with clear success metrics."
            ),
            department=DepartmentName.STRATEGY,
        )

        decision.add_next_action(
            description=(
                "Submit the updated mission for another executive "
                "review."
            ),
            department=DepartmentName.EXECUTIVE,
        )

        decision.decide(
            outcome=DecisionOutcome.REQUIRES_RESEARCH,
            reasoning=(
                "The mission does not contain measurable objectives. "
                "AuraAI cannot reliably plan, track, or declare success "
                "without clearly defined outcomes."
            ),
            confidence_score=0.99,
        )

    def _request_department_selection(
        self,
        *,
        mission: MissionRecord,
        decision: DecisionRecord,
    ) -> None:
        """Request confirmation of the department leading the mission."""

        decision.add_next_action(
            description=(
                "Select the department that will own and coordinate "
                "this mission."
            ),
            department=DepartmentName.EXECUTIVE,
        )

        decision.decide(
            outcome=DecisionOutcome.REQUIRES_USER_INPUT,
            reasoning=(
                "The mission has measurable objectives but no lead "
                "department. Executive ownership must be assigned "
                "before a workflow can be created."
            ),
            confidence_score=0.95,
        )

    def _approve_ready_mission(
        self,
        *,
        mission: MissionRecord,
        decision: DecisionRecord,
    ) -> None:
        """Approve a complete mission and assign its next actions."""

        lead_department = mission.lead_department

        if lead_department is None:
            raise ValidationError(
                "Approved missions must have a lead department.",
                details={
                    "mission_id": str(mission.mission_id),
                },
            )

        decision.add_next_action(
            description=(
                "Create the operational workflow for the approved "
                "mission."
            ),
            department=lead_department,
        )

        decision.add_next_action(
            description=(
                "Submit the workflow plan to the COO for coordination."
            ),
            department=DepartmentName.EXECUTIVE,
        )

        decision.decide(
            outcome=DecisionOutcome.APPROVED,
            reasoning=(
                "The mission has a clear description, measurable "
                "objectives, an assigned lead department, and a "
                "trackable definition of success. It is ready for "
                "workflow planning."
            ),
            confidence_score=0.97,
        )

    @staticmethod
    def _parse_mission(
        mission_value: Any,
    ) -> MissionRecord:
        """Convert supported input into a validated MissionRecord."""

        if isinstance(mission_value, MissionRecord):
            return mission_value

        if isinstance(mission_value, dict):
            try:
                return MissionRecord.model_validate(
                    mission_value
                )
            except Exception as error:
                raise ValidationError(
                    "The supplied mission data is invalid.",
                    details={
                        "exception_type": (
                            error.__class__.__name__
                        ),
                    },
                ) from error

        raise ValidationError(
            "Mission input must be a MissionRecord or dictionary.",
            details={
                "received_type": (
                    mission_value.__class__.__name__
                ),
            },
        )