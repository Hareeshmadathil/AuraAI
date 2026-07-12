"""
Local deterministic research source for AuraAI Creator OS.

This source stores structured records in memory and is useful for tests,
manual research imports, offline development, and fallback operation.
"""

from __future__ import annotations

from collections.abc import Iterable

from core import ValidationError, get_logger
from research_sources.base_source import (
    ResearchQuery,
    ResearchRecord,
    ResearchSource,
)


class LocalResearchSource(ResearchSource):
    """Search a local collection of normalized research records."""

    source_name = "local_research"

    def __init__(
        self,
        records: Iterable[ResearchRecord] | None = None,
    ) -> None:
        self._records: list[ResearchRecord] = list(
            records or []
        )

        self.logger = get_logger(
            "research_sources.local"
        )

    def add_record(
        self,
        record: ResearchRecord,
    ) -> None:
        """Add one normalized local research record."""

        self._records.append(record)

        self.logger.info(
            "Local research record added: %s",
            record.title,
        )

    def search(
        self,
        query: ResearchQuery,
    ) -> list[ResearchRecord]:
        """Return locally stored records matching the query."""

        search_terms = {
            query.topic.casefold(),
            *(
                keyword.casefold()
                for keyword in query.keywords
            ),
        }

        search_terms = {
            term.strip()
            for term in search_terms
            if term.strip()
        }

        if not search_terms:
            raise ValidationError(
                "A local research query requires a topic or keyword."
            )

        scored_results: list[
            tuple[ResearchRecord, float]
        ] = []

        for record in self._records:
            searchable_text = (
                f"{record.title} "
                f"{record.summary}"
            ).casefold()

            matched_terms = sum(
                1
                for term in search_terms
                if term in searchable_text
            )

            if matched_terms == 0:
                continue

            match_ratio = matched_terms / len(
                search_terms
            )

            adjusted_record = record.model_copy(
                update={
                    "relevance_score": round(
                        min(
                            1.0,
                            (
                                record.relevance_score
                                + match_ratio
                            )
                            / 2,
                        ),
                        4,
                    ),
                },
                deep=True,
            )

            scored_results.append(
                (
                    adjusted_record,
                    adjusted_record.combined_score,
                )
            )

        scored_results.sort(
            key=lambda item: (
                -item[1],
                item[0].title.casefold(),
            )
        )

        results = [
            record
            for record, _ in scored_results[
                : query.maximum_results
            ]
        ]

        self.logger.info(
            "Local source search completed: topic=%s | results=%s",
            query.topic,
            len(results),
        )

        return results