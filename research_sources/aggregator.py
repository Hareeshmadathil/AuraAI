"""
Research-source aggregation for AuraAI Creator OS.

The aggregator searches multiple independent adapters, isolates source
failures, deduplicates records, and returns ranked normalized evidence.
"""

from __future__ import annotations

from core import OperationResult, get_logger
from research_sources.base_source import (
    ResearchQuery,
    ResearchRecord,
    ResearchSource,
)


class ResearchSourceAggregator:
    """Coordinate searches across registered research sources."""

    def __init__(
        self,
        sources: list[ResearchSource] | None = None,
    ) -> None:
        self._sources: dict[str, ResearchSource] = {}
        self.logger = get_logger(
            "research_sources.aggregator"
        )

        for source in sources or []:
            self.register_source(source)

    def register_source(
        self,
        source: ResearchSource,
    ) -> None:
        """Register or replace a source by its unique name."""

        source_name = source.source_name.strip()

        if not source_name:
            raise ValueError(
                "Research sources require a source_name."
            )

        self._sources[source_name] = source

        self.logger.info(
            "Research source registered: %s",
            source_name,
        )

    def remove_source(
        self,
        source_name: str,
    ) -> ResearchSource:
        """Remove and return a registered research source."""

        clean_name = source_name.strip()

        try:
            source = self._sources.pop(clean_name)
        except KeyError as error:
            raise ValueError(
                f"Research source '{clean_name}' is not registered."
            ) from error

        self.logger.info(
            "Research source removed: %s",
            clean_name,
        )

        return source

    def list_sources(self) -> list[str]:
        """Return registered source names alphabetically."""

        return sorted(self._sources)

    def search(
        self,
        query: ResearchQuery,
    ) -> OperationResult:
        """
        Search every healthy source and return ranked evidence.

        One failed source does not stop the entire research operation.
        """

        collected_records: list[ResearchRecord] = []
        source_errors: list[dict[str, str]] = []

        for source_name, source in self._sources.items():
            try:
                if not source.health_check():
                    source_errors.append(
                        {
                            "source": source_name,
                            "error": "Source health check failed.",
                        }
                    )
                    continue

                collected_records.extend(
                    source.search(query)
                )

            except Exception as error:
                source_errors.append(
                    {
                        "source": source_name,
                        "error": str(error),
                        "exception_type": (
                            error.__class__.__name__
                        ),
                    }
                )

                self.logger.exception(
                    "Research source failed: %s",
                    source_name,
                )

        ranked_records = self._deduplicate_and_rank(
            collected_records,
            maximum_results=query.maximum_results,
        )

        if not ranked_records and source_errors:
            return OperationResult.failure(
                "All available research sources failed.",
                error_code="RESEARCH_SOURCES_FAILED",
                retryable=True,
                data={
                    "records": [],
                    "source_errors": source_errors,
                },
            )

        return OperationResult.ok(
            "Research-source aggregation completed.",
            data={
                "query_id": str(query.query_id),
                "record_count": len(ranked_records),
                "records": [
                    record.model_dump(mode="json")
                    for record in ranked_records
                ],
                "source_errors": source_errors,
                "sources_searched": len(self._sources),
            },
        )

    @staticmethod
    def _deduplicate_and_rank(
        records: list[ResearchRecord],
        *,
        maximum_results: int,
    ) -> list[ResearchRecord]:
        """Deduplicate by source reference or normalized title."""

        unique_records: dict[
            tuple[str, str],
            ResearchRecord,
        ] = {}

        for record in records:
            identity = (
                record.source_name.casefold(),
                (
                    record.source_reference
                    or record.title
                ).strip().casefold(),
            )

            existing = unique_records.get(identity)

            if (
                existing is None
                or record.combined_score
                > existing.combined_score
            ):
                unique_records[identity] = record

        ranked_records = sorted(
            unique_records.values(),
            key=lambda record: (
                -record.combined_score,
                -record.relevance_score,
                record.title.casefold(),
            ),
        )

        return ranked_records[:maximum_results]


research_source_aggregator = ResearchSourceAggregator()