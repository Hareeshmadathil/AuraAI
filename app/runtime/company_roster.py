"""Neutral factory for AuraAI's currently implemented company roster."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from agents.base_employee import BaseEmployee
from agents.directors import ResearchDirector, StrategyDirector
from agents.executive import AuraCEO, AuraCOO
from agents.specialists import (
    InstagramManager,
    SEOSpecialist,
    TikTokManager,
    TrendHunter,
    YouTubeManager,
)
from marketing import MarketingDirector


@dataclass(frozen=True, slots=True)
class CompanyRoster:
    """Immutable grouping of implemented AuraAI employee instances."""

    executives: tuple[BaseEmployee, ...]
    directors: tuple[BaseEmployee, ...]
    specialists: tuple[BaseEmployee, ...]

    def __post_init__(self) -> None:
        """Reject accidental duplicate employee identifiers."""

        agent_ids = [employee.agent_id for employee in self.employees]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Company roster contains duplicate agent IDs.")

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        """Return every employee in organizational order."""

        return self.executives + self.directors + self.specialists


def create_company_roster() -> CompanyRoster:
    """Construct the current AuraAI company from existing classes."""

    roster = CompanyRoster(
        executives=(AuraCEO(), AuraCOO()),
        directors=(
            StrategyDirector(),
            ResearchDirector(),
            MarketingDirector(),
        ),
        specialists=(
            TrendHunter(),
            SEOSpecialist(),
            YouTubeManager(),
            InstagramManager(),
            TikTokManager(),
        ),
    )

    for employee in roster.employees:
        employee.identity.agent_id = uuid5(
            NAMESPACE_URL,
            f"https://auraai.local/employees/{employee.job_title}",
        )

    return roster
