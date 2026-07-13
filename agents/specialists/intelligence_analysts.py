"""Specialist employees for AuraAI Intelligence Department v1."""

from __future__ import annotations

from collections.abc import Callable

from agents.base_employee import BaseEmployee
from core import AuraBaseModel, DepartmentName, OperationResult, TaskRecord
from intelligence.providers import IntelligenceProvider
from intelligence.task_inputs import require_niche
from providers import PromptCategory, ProviderCapability, build_department_prompt


class _IntelligenceAnalyst(BaseEmployee):
    """Centralized deterministic employee behavior for report specialists."""

    def __init__(
        self,
        *,
        name: str,
        job_title: str,
        description: str,
        provider: IntelligenceProvider,
        output_key: str,
        analyzer: Callable[[str], AuraBaseModel],
    ) -> None:
        super().__init__(
            name=name,
            job_title=job_title,
            department=DepartmentName.INTELLIGENCE,
            description=description,
        )
        self.provider = provider
        self.output_key = output_key
        self._analyzer = analyzer

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Produce one typed report from explicit task input."""

        niche = require_niche(task)
        report = self._analyzer(niche)
        provider_result = self.request_provider(
            ProviderCapability.AUDIENCE,
            build_department_prompt(
                "intelligence_audience_advisory",
                PromptCategory.RESEARCH,
                niche,
            ),
        )
        return OperationResult.ok(
            f"{self.job_title} analysis completed.",
            data={
                self.output_key: report.model_dump(mode="json"),
                **(
                    {"provider_advisory": provider_result.model_dump(mode="json")}
                    if provider_result is not None
                    else {}
                ),
            },
        )


class TrendAnalyst(_IntelligenceAnalyst):
    def __init__(self, provider: IntelligenceProvider) -> None:
        super().__init__(
            name="Signal",
            job_title="Trend Analyst",
            description="Evaluates deterministic topic direction and opportunity.",
            provider=provider,
            output_key="trend_report",
            analyzer=provider.analyze_trends,
        )


class CompetitorAnalyst(_IntelligenceAnalyst):
    def __init__(self, provider: IntelligenceProvider) -> None:
        super().__init__(
            name="Prism",
            job_title="Competitor Analyst",
            description="Maps competitor archetypes and content gaps.",
            provider=provider,
            output_key="competitor_report",
            analyzer=provider.analyze_competitors,
        )


class AudienceAnalyst(_IntelligenceAnalyst):
    def __init__(self, provider: IntelligenceProvider) -> None:
        super().__init__(
            name="Pulse",
            job_title="Audience Analyst",
            description="Builds a deterministic audience persona.",
            provider=provider,
            output_key="audience_persona",
            analyzer=provider.build_audience_persona,
        )


class RetentionEngineer(_IntelligenceAnalyst):
    def __init__(self, provider: IntelligenceProvider) -> None:
        super().__init__(
            name="Anchor",
            job_title="Retention Engineer",
            description="Analyzes hooks, pacing, and retention risks.",
            provider=provider,
            output_key="hook_analysis",
            analyzer=provider.analyze_hooks,
        )


class ThumbnailAnalyst(_IntelligenceAnalyst):
    def __init__(self, provider: IntelligenceProvider) -> None:
        super().__init__(
            name="Focus",
            job_title="Thumbnail Analyst",
            description="Evaluates deterministic thumbnail concepts and clarity.",
            provider=provider,
            output_key="thumbnail_analysis",
            analyzer=provider.analyze_thumbnail,
        )
