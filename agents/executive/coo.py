"""
Chief Operating Officer for AuraAI Creator OS.

The COO converts approved executive missions into organized operational
work. The COO manages the mission queue, creates workflow plans, links
workflows back to missions, and returns structured operational reports.

The COO does not perform specialist work. Research, writing, production,
publishing, and analytics remain the responsibility of departments and
specialist employees.
"""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from core import (
    DepartmentName,
    MissionRecord,
    MissionStatus,
    OperationResult,
    TaskRecord,
    ValidationError,
)
from operations import (
    OperationQueue,
    PlannedWorkflow,
    WorkflowPlanner,
)


class AuraCOO(BaseEmployee):
    """
    Chief Operating Officer of AuraAI Creator OS.

    Responsibilities:

    - receive approved missions;
    - organize missions by priority;
    - create operational workflows;
    - link workflows to their missions;
    - coordinate execution readiness;
    - report operational plans to Aura CEO.
    """

    def __init__(
        self,
        *,
        operation_queue: OperationQueue | None = None,
        workflow_planner: WorkflowPlanner | None = None,
    ) -> None:
        super().__init__(
            name="Orion",
            job_title="Chief Operating Officer",
            department=DepartmentName.EXECUTIVE,
            description=(
                "Runs AuraAI's daily operations, prioritizes approved "
                "missions, creates workflows, coordinates departments, "
                "and reports operational progress to Aura CEO."
            ),
        )

        self.operation_queue = (
            operation_queue
            if operation_queue is not None
            else OperationQueue()
        )

        self.workflow_planner = (
            workflow_planner
            if workflow_planner is not None
            else WorkflowPlanner()
        )

        self._active_workflows: dict[str, PlannedWorkflow] = {}

    @property
    def queued_mission_count(self) -> int:
        """Return the number of missions waiting for planning."""

        return self.operation_queue.count()

    @property
    def active_workflow_count(self) -> int:
        """Return the number of workflows created by this COO."""

        return len(self._active_workflows)

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        """
        Execute a COO operational request.

        Supported operations:

        ``coordinate_mission``
            Queue an approved mission and immediately create its
            workflow.

        ``queue_mission``
            Add an approved mission to the operations queue.

        ``plan_next_mission``
            Remove the next mission from the queue and create its
            workflow.

        Input example:

        ``task.input_data["operation"] = "coordinate_mission"``

        ``task.input_data["mission"] = MissionRecord(...)``
        """

        operation = str(
            task.input_data.get(
                "operation",
                "coordinate_mission",
            )
        ).strip().lower()

        if operation == "queue_mission":
            mission = self._require_mission(task.input_data)
            self.queue_mission(mission)

            return OperationResult.ok(
                "COO added the mission to the operations queue.",
                data={
                    "mission_id": str(mission.mission_id),
                    "mission_title": mission.title,
                    "queued_missions": self.queued_mission_count,
                },
            )

        if operation == "plan_next_mission":
            workflow = self.plan_next_mission()

            return OperationResult.ok(
                "COO created the next operational workflow.",
                data=self._serialize_workflow(workflow),
            )

        if operation == "coordinate_mission":
            mission = self._require_mission(task.input_data)
            workflow = self.coordinate_mission(mission)

            return OperationResult.ok(
                "COO coordinated the approved mission.",
                data={
                    "mission_id": str(mission.mission_id),
                    "mission_title": mission.title,
                    "mission_status": mission.status.value,
                    "workflow": self._serialize_workflow(
                        workflow
                    ),
                },
            )

        raise ValidationError(
            "Unsupported COO operation.",
            details={
                "operation": operation,
                "supported_operations": [
                    "coordinate_mission",
                    "queue_mission",
                    "plan_next_mission",
                ],
            },
        )

    def queue_mission(
        self,
        mission: MissionRecord,
    ) -> None:
        """
        Add one approved mission to the operations queue.
        """

        self.operation_queue.enqueue(mission)

        self.logger.info(
            "COO queued mission: %s | mission_id=%s",
            mission.title,
            mission.mission_id,
        )

    def plan_next_mission(self) -> PlannedWorkflow:
        """
        Create a workflow for the next queued mission.

        Returns:
            Executable workflow created by the workflow planner.
        """

        mission = self.operation_queue.dequeue()

        workflow = self.workflow_planner.create_workflow(
            mission
        )

        if mission.status == MissionStatus.APPROVED:
            mission.begin_planning()

        mission.add_workflow(workflow.workflow_id)

        self._active_workflows[
            str(workflow.workflow_id)
        ] = workflow

        self.logger.info(
            "COO planned mission: %s | mission_id=%s "
            "| workflow_id=%s",
            mission.title,
            mission.mission_id,
            workflow.workflow_id,
        )

        return workflow

    def coordinate_mission(
        self,
        mission: MissionRecord,
    ) -> PlannedWorkflow:
        """
        Queue and immediately plan one approved mission.
        """

        self.queue_mission(mission)
        return self.plan_next_mission()

    def get_active_workflow(
        self,
        workflow_id: str,
    ) -> PlannedWorkflow:
        """
        Return one workflow created by the COO.

        Raises:
            ValidationError:
                If the workflow is unknown.
        """

        clean_workflow_id = workflow_id.strip()

        try:
            return self._active_workflows[
                clean_workflow_id
            ]
        except KeyError as error:
            raise ValidationError(
                "COO workflow was not found.",
                details={
                    "workflow_id": clean_workflow_id,
                },
            ) from error

    def list_active_workflows(
        self,
    ) -> list[PlannedWorkflow]:
        """Return workflows created by the COO."""

        return list(self._active_workflows.values())

    @staticmethod
    def _require_mission(
        input_data: dict[str, Any],
    ) -> MissionRecord:
        """
        Extract and validate a mission from task input.
        """

        mission_value = input_data.get("mission")

        if mission_value is None:
            raise ValidationError(
                "COO requires a mission in task.input_data.",
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
                    "The supplied COO mission is invalid.",
                    details={
                        "exception_type": (
                            error.__class__.__name__
                        ),
                    },
                ) from error

        raise ValidationError(
            "COO mission input must be a MissionRecord "
            "or dictionary.",
            details={
                "received_type": (
                    mission_value.__class__.__name__
                ),
            },
        )

    @staticmethod
    def _serialize_workflow(
        workflow: PlannedWorkflow,
    ) -> dict[str, Any]:
        """
        Convert a workflow into dashboard/API-friendly data.
        """

        return {
            "workflow_id": str(workflow.workflow_id),
            "mission_id": (
                str(workflow.mission_id)
                if workflow.mission_id is not None
                else None
            ),
            "name": workflow.name,
            "status": workflow.status.value,
            "progress_percentage": (
                workflow.progress_percentage
            ),
            "step_count": len(workflow.steps),
            "steps": [
                {
                    "step_id": str(step.step_id),
                    "name": step.name,
                    "department": (
                        step.department.value
                    ),
                    "status": step.status.value,
                    "requires_approval": (
                        step.requires_approval
                    ),
                }
                for step in workflow.steps
            ],
        }