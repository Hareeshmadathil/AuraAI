"""
Trend Hunter specialist for AuraAI Creator OS.

The Trend Hunter evaluates structured niche and topic candidates using a
transparent deterministic scoring model. Live trend and platform data
will be connected later through replaceable research-source adapters.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from agents.base_employee import BaseEmployee
from core import (
    AuraBaseModel,
    DepartmentName,
    OperationResult,
    TaskRecord,
    ValidationError,
)


class TrendCandidate(AuraBaseModel):
    """One trend or niche candidate awaiting evaluation."""

    candidate_id: UUID = Field(default_factory=uuid4)

    name: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str = Field(
        default="",
        max_length=5000,
    )

    demand_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    trend_velocity_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    monetization_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    competition_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    production_difficulty_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    evidence: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)


class TrendOpportunity(AuraBaseModel):
    """Scored opportunity produced by the Trend Hunter."""

    candidate_id: UUID

    name: str

    opportunity_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    rank: int = Field(
        ge=1,
    )

    recommendation: str

    score_breakdown: dict[str, float]

    evidence: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)


class TrendHunter(BaseEmployee):
    """
    Specialist responsible for identifying and ranking opportunities.

    The deterministic score weights are intentionally visible and can
    later be configured without changing the employee interface.
    """

    DEMAND_WEIGHT = 0.30
    VELOCITY_WEIGHT = 0.20
    MONETIZATION_WEIGHT = 0.20
    COMPETITION_WEIGHT = 0.15
    PRODUCTION_WEIGHT = 0.15

    def __init__(self) -> None:
        super().__init__(
            name="Scout",
            job_title="Trend Hunter",
            department=DepartmentName.RESEARCH,
            description=(
                "Discovers and scores emerging niches and topics using "
                "audience demand, momentum, monetization, competition, "
                "production difficulty, evidence, and risk."
            ),
        )

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        """Rank candidate opportunities supplied through task input."""

        candidate_values = task.input_data.get("candidates")

        if candidate_values is None:
            raise ValidationError(
                "Trend Hunter requires candidates in task.input_data.",
                details={
                    "required_key": "candidates",
                },
            )

        candidates = self._parse_candidates(
            candidate_values
        )

        opportunities = self.rank_candidates(
            candidates
        )

        return OperationResult.ok(
            "Trend Hunter ranked the supplied opportunities.",
            data={
                "candidate_count": len(candidates),
                "opportunities": [
                    opportunity.model_dump(mode="json")
                    for opportunity in opportunities
                ],
                "recommended_candidate": (
                    opportunities[0].model_dump(mode="json")
                ),
            },
        )

    def rank_candidates(
        self,
        candidates: list[TrendCandidate],
    ) -> list[TrendOpportunity]:
        """Score and rank candidate opportunities."""

        if not candidates:
            raise ValidationError(
                "At least one trend candidate is required."
            )

        scored_candidates: list[
            tuple[TrendCandidate, float, dict[str, float]]
        ] = []

        for candidate in candidates:
            competition_advantage = (
                100.0 - candidate.competition_score
            )

            production_advantage = (
                100.0
                - candidate.production_difficulty_score
            )

            breakdown = {
                "demand": round(
                    candidate.demand_score
                    * self.DEMAND_WEIGHT,
                    2,
                ),
                "trend_velocity": round(
                    candidate.trend_velocity_score
                    * self.VELOCITY_WEIGHT,
                    2,
                ),
                "monetization": round(
                    candidate.monetization_score
                    * self.MONETIZATION_WEIGHT,
                    2,
                ),
                "competition_advantage": round(
                    competition_advantage
                    * self.COMPETITION_WEIGHT,
                    2,
                ),
                "production_advantage": round(
                    production_advantage
                    * self.PRODUCTION_WEIGHT,
                    2,
                ),
            }

            opportunity_score = round(
                sum(breakdown.values()),
                2,
            )

            scored_candidates.append(
                (
                    candidate,
                    opportunity_score,
                    breakdown,
                )
            )

        scored_candidates.sort(
            key=lambda item: (
                -item[1],
                item[0].name.casefold(),
            )
        )

        return [
            TrendOpportunity(
                candidate_id=candidate.candidate_id,
                name=candidate.name,
                opportunity_score=score,
                rank=index,
                recommendation=self._build_recommendation(
                    score
                ),
                score_breakdown=breakdown,
                evidence=list(candidate.evidence),
                risks=list(candidate.risks),
            )
            for index, (
                candidate,
                score,
                breakdown,
            ) in enumerate(
                scored_candidates,
                start=1,
            )
        ]

    @staticmethod
    def _build_recommendation(
        opportunity_score: float,
    ) -> str:
        """Convert a score into a transparent recommendation."""

        if opportunity_score >= 80.0:
            return "Strong opportunity — prioritize deeper validation."

        if opportunity_score >= 65.0:
            return "Promising opportunity — continue research."

        if opportunity_score >= 50.0:
            return "Moderate opportunity — proceed cautiously."

        return "Weak opportunity — do not prioritize currently."

    @staticmethod
    def _parse_candidates(
        candidate_values: Any,
    ) -> list[TrendCandidate]:
        """Validate supported candidate input formats."""

        if not isinstance(candidate_values, list):
            raise ValidationError(
                "Trend candidates must be supplied as a list.",
                details={
                    "received_type": (
                        candidate_values.__class__.__name__
                    ),
                },
            )

        candidates: list[TrendCandidate] = []

        for index, candidate_value in enumerate(
            candidate_values
        ):
            if isinstance(
                candidate_value,
                TrendCandidate,
            ):
                candidates.append(candidate_value)
                continue

            if isinstance(candidate_value, dict):
                try:
                    candidates.append(
                        TrendCandidate.model_validate(
                            candidate_value
                        )
                    )
                    continue
                except Exception as error:
                    raise ValidationError(
                        "A trend candidate is invalid.",
                        details={
                            "candidate_index": index,
                            "exception_type": (
                                error.__class__.__name__
                            ),
                        },
                    ) from error

            raise ValidationError(
                "Each trend candidate must be a TrendCandidate "
                "or dictionary.",
                details={
                    "candidate_index": index,
                    "received_type": (
                        candidate_value.__class__.__name__
                    ),
                },
            )

        if not candidates:
            raise ValidationError(
                "At least one trend candidate is required."
            )

        return candidates