"""
Base research-source contracts for AuraAI Creator OS.

External research systems such as YouTube, Google Trends, RSS feeds,
public datasets, and local files must implement these contracts. Agents
consume normalized research records rather than provider-specific data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core import AuraBaseModel, utc_now


class ResearchQuery(AuraBaseModel):
    """Structured query sent to one or more research sources."""

    query_id: UUID = Field(default_factory=uuid4)

    topic: str = Field(
        min_length=1,
        max_length=500,
    )

    keywords: list[str] = Field(default_factory=list)

    region: str | None = Field(
        default=None,
        max_length=100,
    )

    language: str = Field(
        default="en",
        min_length=2,
        max_length=20,
    )

    maximum_results: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    context: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utc_now)


class ResearchRecord(AuraBaseModel):
    """Normalized result returned by any AuraAI research source."""

    record_id: UUID = Field(default_factory=uuid4)

    source_name: str = Field(
        min_length=1,
        max_length=150,
    )

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    summary: str = Field(
        default="",
        max_length=10000,
    )

    source_reference: str | None = Field(
        default=None,
        max_length=3000,
    )

    published_at: datetime | None = None

    relevance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    reliability_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    metadata: dict[str, Any] = Field(default_factory=dict)

    collected_at: datetime = Field(default_factory=utc_now)

    @property
    def combined_score(self) -> float:
        """Return a balanced relevance and reliability score."""

        return round(
            (
                self.relevance_score
                + self.reliability_score
            )
            / 2,
            4,
        )


class ResearchSource(ABC):
    """Abstract parent for every AuraAI research-source adapter."""

    source_name: str

    @abstractmethod
    def search(
        self,
        query: ResearchQuery,
    ) -> list[ResearchRecord]:
        """
        Search this source and return normalized research records.
        """

        raise NotImplementedError

    def health_check(self) -> bool:
        """
        Return whether this source is currently available.

        Sources with external dependencies may override this method.
        """

        return True