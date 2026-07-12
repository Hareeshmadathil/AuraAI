"""
Tests for AuraAI's replaceable research-source layer.
"""

from research_sources import (
    LocalResearchSource,
    ResearchQuery,
    ResearchRecord,
    ResearchSource,
    ResearchSourceAggregator,
)


class FailingResearchSource(ResearchSource):
    """Source used to verify failure isolation."""

    source_name = "failing_source"

    def search(
        self,
        query: ResearchQuery,
    ) -> list[ResearchRecord]:
        raise RuntimeError("Temporary source failure.")


def build_local_source() -> LocalResearchSource:
    """Create deterministic local research evidence."""

    return LocalResearchSource(
        records=[
            ResearchRecord(
                source_name="manual_research",
                title="AI productivity demand among small businesses",
                summary=(
                    "Small businesses are actively exploring practical "
                    "AI automation and productivity workflows."
                ),
                source_reference="local://ai-productivity-demand",
                relevance_score=0.8,
                reliability_score=0.9,
            ),
            ResearchRecord(
                source_name="manual_research",
                title="AI entertainment news",
                summary=(
                    "General entertainment coverage mentioning AI."
                ),
                source_reference="local://ai-entertainment",
                relevance_score=0.4,
                reliability_score=0.6,
            ),
            ResearchRecord(
                source_name="manual_research",
                title="Small-business automation tools",
                summary=(
                    "Practical automation tools can reduce repetitive "
                    "administrative work."
                ),
                source_reference="local://automation-tools",
                relevance_score=0.75,
                reliability_score=0.85,
            ),
        ]
    )


def test_local_source_returns_relevant_records() -> None:
    source = build_local_source()

    query = ResearchQuery(
        topic="small businesses",
        keywords=[
            "AI productivity",
            "automation",
        ],
    )

    results = source.search(query)

    assert len(results) == 2
    assert (
        results[0].title
        == "AI productivity demand among small businesses"
    )
    assert (
        results[0].combined_score
        >= results[1].combined_score
    )


def test_aggregator_collects_and_ranks_records() -> None:
    aggregator = ResearchSourceAggregator(
        sources=[
            build_local_source(),
        ]
    )

    query = ResearchQuery(
        topic="small businesses",
        keywords=["automation"],
        maximum_results=10,
    )

    result = aggregator.search(query)

    assert result.success is True
    assert result.data["record_count"] == 2
    assert result.data["sources_searched"] == 1
    assert result.data["source_errors"] == []


def test_aggregator_isolates_failed_source() -> None:
    aggregator = ResearchSourceAggregator(
        sources=[
            build_local_source(),
            FailingResearchSource(),
        ]
    )

    query = ResearchQuery(
        topic="AI productivity",
    )

    result = aggregator.search(query)

    assert result.success is True
    assert result.data["record_count"] >= 1
    assert len(result.data["source_errors"]) == 1
    assert (
        result.data["source_errors"][0]["source"]
        == "failing_source"
    )


def test_aggregator_reports_total_failure() -> None:
    aggregator = ResearchSourceAggregator(
        sources=[
            FailingResearchSource(),
        ]
    )

    query = ResearchQuery(
        topic="AI productivity",
    )

    result = aggregator.search(query)

    assert result.success is False
    assert (
        result.error_code
        == "RESEARCH_SOURCES_FAILED"
    )
    assert result.retryable is True


def test_source_registration_and_removal() -> None:
    aggregator = ResearchSourceAggregator()
    source = build_local_source()

    aggregator.register_source(source)

    assert aggregator.list_sources() == [
        "local_research"
    ]

    removed = aggregator.remove_source(
        "local_research"
    )

    assert removed is source
    assert aggregator.list_sources() == []