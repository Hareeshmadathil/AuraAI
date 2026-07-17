"""Deterministic comparative content intelligence from canonical evidence."""
from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from core import AuraBaseModel
from web_intelligence.evidence_layer import CanonicalEvidence


class ContentPattern(AuraBaseModel):
    evidence_id: UUID
    topic: str
    hook: str
    title_pattern: str
    thumbnail_pattern: str
    description_pattern: str
    storytelling: str
    pacing: str
    seo_terms: list[str]
    engagement_score: float = Field(ge=0, le=100)
    audience_intent: str


class ContentIntelligenceReport(AuraBaseModel):
    report_id: UUID
    patterns: list[ContentPattern]
    topic_saturation: float = Field(ge=0, le=100)
    opportunity_score: float = Field(ge=0, le=100)
    recommendation: str
    evidence_ids: list[UUID]


class ContentIntelligenceService:
    """Explain why evidence-backed content patterns may succeed."""

    def analyze(self, evidence: list[CanonicalEvidence]) -> ContentIntelligenceReport:
        if not evidence:
            raise ValueError("Canonical evidence is required for content intelligence.")
        patterns = [self._pattern(item) for item in evidence]
        topics = {item.topic.casefold() for item in evidence}
        saturation = round(min(100.0, len(evidence) / max(1, len(topics)) * 25), 2)
        opportunity = round(max(0.0, sum(item.rank_score for item in evidence) / len(evidence) - saturation * 0.15), 2)
        identity = "|".join(sorted(item.content_hash for item in evidence))
        return ContentIntelligenceReport(
            report_id=uuid5(NAMESPACE_URL, f"content-intelligence:{identity}"),
            patterns=patterns,
            topic_saturation=saturation,
            opportunity_score=opportunity,
            recommendation=("Favor concrete evidence-led educational hooks with truthful visual contrast "
                            "and fast problem-to-outcome pacing."),
            evidence_ids=[item.evidence_id for item in evidence],
        )

    @staticmethod
    def _pattern(item: CanonicalEvidence) -> ContentPattern:
        terms = sorted({word.strip(".,:").casefold() for word in item.topic.split() if len(word) > 3})[:8]
        return ContentPattern(
            evidence_id=item.evidence_id,
            topic=item.topic,
            hook=f"Lead with the practical outcome: {item.claim[:120]}",
            title_pattern=f"How {item.topic} works in practice",
            thumbnail_pattern="One truthful outcome phrase with a single high-contrast focal element.",
            description_pattern="Problem, evidence, workflow, outcome, and source citation.",
            storytelling="Problem → evidence → demonstration → founder-controlled next step.",
            pacing="Outcome in the opening; one evidence-backed idea per section.",
            seo_terms=terms,
            engagement_score=round(item.rank_score, 2),
            audience_intent="Learn and apply a credible creator workflow.",
        )
