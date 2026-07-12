"""
Executive decision models for AuraAI Creator OS.

Every important strategic, financial, publishing, operational, or
technology decision is recorded in a structured form. This provides
traceability, explainability, audit history, and later performance
reviews.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core.constants import (
    DecisionOutcome,
    DecisionReviewStatus,
    DecisionType,
    DepartmentName,
)
from core.models import AuraBaseModel, utc_now


_FINAL_DECISION_OUTCOMES = {
    DecisionOutcome.APPROVED,
    DecisionOutcome.REJECTED,
    DecisionOutcome.DEFERRED,
    DecisionOutcome.REQUIRES_RESEARCH,
    DecisionOutcome.REQUIRES_USER_INPUT,
    DecisionOutcome.ESCALATED,
    DecisionOutcome.AUTOMATED,
}


class DecisionEvidence(AuraBaseModel):
    """One piece of evidence supporting an executive decision."""

    evidence_id: UUID = Field(default_factory=uuid4)

    title: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str = Field(
        min_length=1,
        max_length=5000,
    )

    source_type: str = Field(
        default="internal",
        min_length=1,
        max_length=100,
    )

    source_reference: str | None = Field(
        default=None,
        max_length=2000,
    )

    reliability_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utc_now)


class DecisionAction(AuraBaseModel):
    """One follow-up action created by an executive decision."""

    action_id: UUID = Field(default_factory=uuid4)

    description: str = Field(
        min_length=1,
        max_length=2000,
    )

    department: DepartmentName | None = None

    assigned_agent_id: UUID | None = None

    completed: bool = False

    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    def mark_completed(self) -> None:
        """Mark the follow-up action as completed."""

        now = utc_now()

        object.__setattr__(self, "completed", True)
        object.__setattr__(self, "completed_at", now)
        object.__setattr__(self, "updated_at", now)

    def reopen(self) -> None:
        """Reopen a previously completed follow-up action."""

        object.__setattr__(self, "completed", False)
        object.__setattr__(self, "completed_at", None)
        object.__setattr__(self, "updated_at", utc_now())


class DecisionRecord(AuraBaseModel):
    """
    Structured executive decision created inside AuraAI.

    A decision may belong to a mission, workflow, department, or task.
    It records evidence, reasoning, confidence, next actions, user
    confirmation, and a later review of the real outcome.
    """

    decision_id: UUID = Field(default_factory=uuid4)

    title: str = Field(
        min_length=1,
        max_length=250,
    )

    decision_type: DecisionType

    outcome: DecisionOutcome = DecisionOutcome.PENDING

    decision_maker_agent_id: UUID | None = None

    decision_maker_name: str = Field(
        default="Aura",
        min_length=1,
        max_length=150,
    )

    mission_id: UUID | None = None
    workflow_id: UUID | None = None
    task_id: UUID | None = None

    department: DepartmentName = DepartmentName.EXECUTIVE

    context: dict[str, Any] = Field(default_factory=dict)

    evidence: list[DecisionEvidence] = Field(default_factory=list)

    reasoning: str = Field(
        default="",
        max_length=10000,
    )

    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    next_actions: list[DecisionAction] = Field(default_factory=list)

    requires_user_confirmation: bool = False

    user_confirmed: bool = False

    review_status: DecisionReviewStatus = (
        DecisionReviewStatus.NOT_REVIEWED
    )

    review_notes: str = Field(
        default="",
        max_length=10000,
    )

    actual_outcome: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    reviewed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_decision_state(self) -> "DecisionRecord":
        """Validate logical relationships between decision fields."""

        if (
            self.outcome != DecisionOutcome.PENDING
            and not self.reasoning.strip()
        ):
            raise ValueError(
                "A completed decision must include reasoning."
            )

        if (
            self.outcome != DecisionOutcome.PENDING
            and self.decided_at is None
        ):
            raise ValueError(
                "A completed decision must include decided_at."
            )

        if (
            self.user_confirmed
            and not self.requires_user_confirmation
        ):
            raise ValueError(
                "user_confirmed cannot be true when user confirmation "
                "was not required."
            )

        if (
            self.review_status
            != DecisionReviewStatus.NOT_REVIEWED
            and self.reviewed_at is None
        ):
            raise ValueError(
                "A reviewed decision must include reviewed_at."
            )

        if (
            self.review_status
            != DecisionReviewStatus.NOT_REVIEWED
            and not self.review_notes.strip()
        ):
            raise ValueError(
                "A reviewed decision must include review notes."
            )

        return self

    @property
    def is_final(self) -> bool:
        """Return whether the decision has a final outcome."""

        return self.outcome in _FINAL_DECISION_OUTCOMES

    @property
    def confidence_percentage(self) -> float:
        """Return confidence as a dashboard percentage."""

        return round(self.confidence_score * 100, 2)

    @property
    def completed_actions(self) -> int:
        """Return the number of completed follow-up actions."""

        return sum(
            1
            for action in self.next_actions
            if action.completed
        )

    @property
    def action_progress_percentage(self) -> float:
        """Return completion progress of follow-up actions."""

        if not self.next_actions:
            return 0.0

        return round(
            self.completed_actions
            / len(self.next_actions)
            * 100,
            2,
        )

    def add_evidence(
        self,
        *,
        title: str,
        description: str,
        source_type: str = "internal",
        source_reference: str | None = None,
        reliability_score: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEvidence:
        """Create and attach supporting evidence."""

        evidence = DecisionEvidence(
            title=title,
            description=description,
            source_type=source_type,
            source_reference=source_reference,
            reliability_score=reliability_score,
            metadata=metadata or {},
        )

        self.evidence.append(evidence)
        self.updated_at = utc_now()

        return evidence

    def add_next_action(
        self,
        *,
        description: str,
        department: DepartmentName | None = None,
        assigned_agent_id: UUID | None = None,
    ) -> DecisionAction:
        """Create and attach one follow-up action."""

        action = DecisionAction(
            description=description,
            department=department,
            assigned_agent_id=assigned_agent_id,
        )

        self.next_actions.append(action)
        self.updated_at = utc_now()

        return action

    def decide(
        self,
        *,
        outcome: DecisionOutcome,
        reasoning: str,
        confidence_score: float,
    ) -> None:
        """
        Finalize the executive decision.

        Related scalar fields are updated together without replacing
        nested evidence or action objects.
        """

        if self.is_final:
            raise ValueError(
                "A finalized decision cannot be decided again."
            )

        if outcome == DecisionOutcome.PENDING:
            raise ValueError(
                "A final decision outcome cannot remain pending."
            )

        clean_reasoning = reasoning.strip()

        if not clean_reasoning:
            raise ValueError(
                "Decision reasoning is required."
            )

        if not 0.0 <= confidence_score <= 1.0:
            raise ValueError(
                "confidence_score must be between 0.0 and 1.0."
            )

        now = utc_now()

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "reasoning", clean_reasoning)
        object.__setattr__(
            self,
            "confidence_score",
            confidence_score,
        )
        object.__setattr__(self, "decided_at", now)
        object.__setattr__(self, "updated_at", now)

        self.__class__.model_validate(self.model_dump())

    def confirm_by_user(self) -> None:
        """Record required user confirmation."""

        if not self.requires_user_confirmation:
            raise ValueError(
                "This decision does not require user confirmation."
            )

        if not self.is_final:
            raise ValueError(
                "A pending decision cannot be confirmed."
            )

        now = utc_now()

        object.__setattr__(self, "user_confirmed", True)
        object.__setattr__(self, "updated_at", now)

        self.__class__.model_validate(self.model_dump())

    def review(
        self,
        *,
        status: DecisionReviewStatus,
        notes: str,
        actual_outcome: dict[str, Any] | None = None,
    ) -> None:
        """Review whether the decision produced the expected result."""

        if not self.is_final:
            raise ValueError(
                "Only finalized decisions can be reviewed."
            )

        if status == DecisionReviewStatus.NOT_REVIEWED:
            raise ValueError(
                "A completed review requires a final review status."
            )

        clean_notes = notes.strip()

        if not clean_notes:
            raise ValueError(
                "Review notes are required."
            )

        now = utc_now()

        object.__setattr__(self, "review_status", status)
        object.__setattr__(self, "review_notes", clean_notes)
        object.__setattr__(
            self,
            "actual_outcome",
            dict(actual_outcome or {}),
        )
        object.__setattr__(self, "reviewed_at", now)
        object.__setattr__(self, "updated_at", now)

        self.__class__.model_validate(self.model_dump())