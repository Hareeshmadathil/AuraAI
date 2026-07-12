"""
Public interface for AuraAI research-source adapters.
"""

from research_sources.aggregator import (
    ResearchSourceAggregator,
    research_source_aggregator,
)
from research_sources.base_source import (
    ResearchQuery,
    ResearchRecord,
    ResearchSource,
)
from research_sources.local_source import (
    LocalResearchSource,
)

__all__ = [
    "LocalResearchSource",
    "ResearchQuery",
    "ResearchRecord",
    "ResearchSource",
    "ResearchSourceAggregator",
    "research_source_aggregator",
]