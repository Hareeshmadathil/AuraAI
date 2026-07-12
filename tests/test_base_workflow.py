"""
Tests for AuraAI's base workflow engine.
"""

from core.constants import (
    DepartmentName,
    JobStatus,
)
from workflows.base_workflow import BaseWorkflow


class NicheDiscoveryWorkflow(BaseWorkflow):
    """Test workflow representing AuraAI's first strategy mission."""

    def build_steps(self) -> None:
        research_step = self.add_step(
            name="Research promising niches",
            description=(
                "Identify sustainable content niches with audience "
                "demand and monetization potential."
            ),
            department=DepartmentName.RESEARCH,
        )

        analysis_step = self.add_step(
            name="Analyze niche opportunities",
            description=(
                "Score demand, competition, production difficulty, "
                "and revenue potential."
            ),
            department=DepartmentName.STRATEGY,
            dependency_step_ids=[research_step.step_id],
        )

        self.add_step(
            name="Approve final niche",
            description=(
                "Review the recommendation and approve one niche."
            ),
            department=DepartmentName.EXECUTIVE,
            dependency_step_ids=[analysis_step.step_id],
            requires_approval=True,
        )


def test_workflow_lifecycle() -> None:
    workflow = NicheDiscoveryWorkflow(
        name="AuraAI Niche Discovery",
        description="Select AuraAI's first content niche.",
    )

    assert workflow.status == JobStatus.CREATED
    assert len(workflow.steps) == 3
    assert workflow.progress_percentage == 0.0

    workflow.start()

    assert workflow.status == JobStatus.RUNNING

    ready_steps = workflow.get_ready_steps()

    assert len(ready_steps) == 1
    assert ready_steps[0].name == "Research promising niches"

    first_step = workflow.start_step(
        ready_steps[0].step_id
    )

    assert first_step.status == JobStatus.RUNNING

    workflow.complete_step(
        first_step.step_id,
        output_data={
            "niches_found": 20,
        },
    )

    assert workflow.progress_percentage == 33.33

    second_step = workflow.get_ready_steps()[0]

    workflow.start_step(second_step.step_id)

    workflow.complete_step(
        second_step.step_id,
        output_data={
            "recommended_niche": "AI productivity",
        },
    )

    assert workflow.progress_percentage == 66.67

    approval_step = workflow.steps[2]

    assert workflow.get_ready_steps() == []

    approval_step.approve()

    assert workflow.get_ready_steps() == [
        approval_step
    ]

    workflow.start_step(approval_step.step_id)

    workflow.complete_step(
        approval_step.step_id,
        output_data={
            "approved": True,
        },
    )

    assert workflow.progress_percentage == 100.0
    assert workflow.status == JobStatus.COMPLETED


def test_workflow_retry() -> None:
    workflow = NicheDiscoveryWorkflow(
        name="Retry Test Workflow",
    )

    workflow.start()

    first_step = workflow.get_ready_steps()[0]

    workflow.start_step(first_step.step_id)

    workflow.fail_step(
        first_step.step_id,
        error_message="Temporary research provider failure.",
        retryable=True,
    )

    assert first_step.status == JobStatus.QUEUED
    assert first_step.retry_count == 1
    assert workflow.status == JobStatus.RUNNING

    workflow.start_step(first_step.step_id)

    workflow.complete_step(
        first_step.step_id,
        output_data={
            "recovered": True,
        },
    )

    assert first_step.status == JobStatus.COMPLETED