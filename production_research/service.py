"""Application service for offline AI production-provider evaluation."""

from __future__ import annotations

from core import get_logger

from production_research.catalog import ProviderCatalog, create_placeholder_catalog
from production_research.models import (
    ProviderCategory,
    ProviderCategorySummary,
    ProviderRecord,
    ProviderResearchReport,
    ProviderStatus,
)
from production_research.scoring import ProviderScorer


class ProductionResearchService:
    """Build reports from an injected catalog without external state or I/O."""

    def __init__(self, catalog: ProviderCatalog | None = None) -> None:
        self._catalog = catalog or create_placeholder_catalog()
        self._logger = get_logger(__name__)

    def list_categories(self) -> list[ProviderCategory]:
        """Return every supported category in enum order."""

        return list(ProviderCategory)

    def list_providers(
        self,
        category: ProviderCategory | None = None,
    ) -> list[ProviderRecord]:
        """Return deterministic candidate rankings, optionally by category."""

        return self._catalog.list_providers(category)

    def show_provider(self, name: str) -> ProviderRecord:
        """Return one exact catalog record."""

        return self._catalog.get_provider(name)

    def build_report(self) -> ProviderResearchReport:
        """Build a typed offline report without network requests."""

        providers = self.list_providers()
        summaries = [
            self._summarize_category(category, providers)
            for category in self.list_categories()
        ]
        self._logger.info(
            "Built offline production-research report with %d providers.",
            len(providers),
        )
        return ProviderResearchReport(
            methodology=ProviderScorer.METHODOLOGY,
            data_notice=(
                "PLACEHOLDER / MANUALLY MAINTAINED DATA. No live scraping, API "
                "calls, pricing verification, or provider performance tests occurred."
            ),
            categories=summaries,
            providers=providers,
        )

    @staticmethod
    def _summarize_category(
        category: ProviderCategory,
        providers: list[ProviderRecord],
    ) -> ProviderCategorySummary:
        matching = [item for item in providers if item.category == category]
        approved = [item for item in matching if item.status == ProviderStatus.APPROVED]
        ranked = sorted(matching, key=lambda item: (-item.local_score, item.name))
        return ProviderCategorySummary(
            category=category,
            provider_count=len(matching),
            approved_count=len(approved),
            average_score=(
                round(sum(item.local_score for item in matching) / len(matching), 2)
                if matching
                else 0
            ),
            recommended_provider=ranked[0].name if ranked else None,
        )
