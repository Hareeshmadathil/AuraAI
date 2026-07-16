"""Canonical evidence composition for offline and future web extraction."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from agents.specialists.trend_hunter import TrendCandidate
from core import AuraBaseModel, utc_now
from intelligence_director.contradiction_detection import detect_contradiction
from intelligence_director.enums import FreshnessStatus, SignalSource, VerificationStatus
from intelligence_director.freshness import assess_freshness
from intelligence_director.models import (
    ContradictionGroup,
    EvidenceConflict,
    FreshnessAssessment,
    IntelligenceSignal,
    SignalContext,
    SourceAuthorityAssessment,
)
from intelligence_director.source_authority import assess_source
from web_intelligence.models import Citation


class EvidenceDraft(AuraBaseModel):
    """Provider-neutral input accepted from fixtures or future adapters."""

    public_source: str = Field(min_length=1, max_length=1000)
    source_title: str = Field(min_length=1, max_length=500)
    source_category: str = Field(min_length=1, max_length=100)
    observed_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    topic: str = Field(min_length=1, max_length=500)
    entities: list[str] = Field(default_factory=list)
    claim: str = Field(min_length=1, max_length=1500)
    excerpt: str = Field(min_length=1, max_length=500)
    freshness_category: str = Field(default="general", max_length=100)
    provenance: dict[str, Any] = Field(default_factory=dict)
    contradicts_claims: list[str] = Field(default_factory=list)


class CanonicalEvidence(AuraBaseModel):
    """One immutable, citation-bound evidence record."""

    evidence_id: UUID
    public_source: str
    source_title: str
    source_authority: SourceAuthorityAssessment
    observed_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    topic: str
    entities: list[str]
    claim: str
    excerpt: str
    freshness: FreshnessAssessment
    contradictions: list[ContradictionGroup] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    citation: Citation
    rank_score: float = Field(ge=0.0, le=100.0)


class EvidenceLayer:
    """Normalize, deduplicate, assess, and rank canonical evidence."""

    _FRESHNESS_WEIGHTS = {
        FreshnessStatus.FRESH: 1.0,
        FreshnessStatus.DUE: 0.8,
        FreshnessStatus.STALE: 0.5,
        FreshnessStatus.EXPIRED: 0.1,
        FreshnessStatus.SUPERSEDED: 0.0,
    }

    def __init__(self, *, now: datetime | None = None) -> None:
        self.now = now or utc_now()

    def build(self, drafts: list[EvidenceDraft]) -> list[CanonicalEvidence]:
        """Return unique evidence ordered by transparent rank score."""

        unique: dict[str, EvidenceDraft] = {}
        for draft in drafts:
            unique.setdefault(self._hash(draft), draft)
        values = [self._compose(draft, digest) for digest, draft in unique.items()]
        return sorted(values, key=lambda item: (-item.rank_score, item.content_hash))

    def candidates(self, evidence: list[CanonicalEvidence]) -> list[TrendCandidate]:
        """Project ranked evidence topics into the existing Trend Hunter contract."""

        topics: dict[str, list[CanonicalEvidence]] = {}
        for item in evidence:
            topics.setdefault(item.topic.strip().casefold(), []).append(item)
        candidates = []
        for key in sorted(topics):
            items = topics[key]
            score = round(sum(item.rank_score for item in items) / len(items), 2)
            freshness = round(
                sum(self._FRESHNESS_WEIGHTS[item.freshness.status] for item in items)
                / len(items)
                * 100,
                2,
            )
            candidates.append(
                TrendCandidate(
                    name=items[0].topic,
                    description=items[0].claim,
                    demand_score=score,
                    trend_velocity_score=freshness,
                    monetization_score=min(100.0, score * 0.85),
                    competition_score=50.0,
                    production_difficulty_score=35.0,
                    evidence=[item.citation.url for item in items],
                    risks=[
                        group.summary
                        for item in items
                        for group in item.contradictions
                    ],
                )
            )
        return candidates

    def fixtures(self, founder_goal: str) -> list[CanonicalEvidence]:
        """Build deterministic public-source fixtures without network access."""

        goal = founder_goal.rstrip(". ")
        observed = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
        drafts = [
            EvidenceDraft(
                public_source="https://example.com/auraai/education",
                source_title="AuraAI educational workflow fixture",
                source_category="official_primary",
                observed_at=observed,
                confidence=0.86,
                topic=f"{goal}: practical education",
                entities=["AuraAI", "creators"],
                claim="Practical, evidence-aware educational workflows are suitable for an offline content pilot.",
                excerpt="Deterministic public-source fixture for practical education.",
                freshness_category="evergreen",
                provenance={"fixture": "mission-generator-v1", "offline": True},
            ),
            EvidenceDraft(
                public_source="https://example.com/auraai/case-study",
                source_title="AuraAI workflow case-study fixture",
                source_category="reputable_secondary",
                observed_at=observed,
                confidence=0.76,
                topic=f"{goal}: workflow case study",
                entities=["AuraAI", "workflows"],
                claim="A documented workflow case study can create founder-controlled learning value.",
                excerpt="Deterministic public-source fixture for a workflow case study.",
                freshness_category="evergreen",
                provenance={"fixture": "mission-generator-v1", "offline": True},
            ),
            EvidenceDraft(
                public_source="https://example.com/auraai/briefing",
                source_title="AuraAI founder briefing fixture",
                source_category="founder_supplied",
                observed_at=observed,
                confidence=0.65,
                topic=f"{goal}: founder briefing",
                entities=["AuraAI", "founder"],
                claim="A concise briefing offers internal value but limited public evidence.",
                excerpt="Deterministic public-source fixture for a founder briefing.",
                freshness_category="general",
                provenance={"fixture": "mission-generator-v1", "offline": True},
            ),
        ]
        return self.build(drafts)

    def from_candidates(
        self, candidates: list[TrendCandidate]
    ) -> list[CanonicalEvidence]:
        """Preserve the existing generator test/injection interface."""

        observed = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
        drafts = [
            EvidenceDraft(
                public_source=f"fixture://trend/{index}",
                source_title=f"Injected trend candidate: {item.name}",
                source_category="founder_supplied",
                observed_at=observed,
                confidence=max(0.2, min(0.95, item.demand_score / 100)),
                topic=item.name,
                entities=[],
                claim=item.description or item.name,
                excerpt="; ".join(item.evidence) or "Injected deterministic candidate.",
                freshness_category="evergreen",
                provenance={"adapter": "legacy-trend-candidate", "offline": True},
            )
            for index, item in enumerate(candidates)
        ]
        return self.build(drafts)

    def _compose(self, draft: EvidenceDraft, digest: str) -> CanonicalEvidence:
        evidence_id = uuid5(NAMESPACE_URL, f"evidence:{digest}")
        signal = IntelligenceSignal(
            signal_id=evidence_id,
            source=SignalSource.FIXTURE,
            source_name=draft.source_title,
            topic=draft.topic,
            summary=draft.claim,
            entities=draft.entities,
            evidence_references=[draft.public_source],
            observed_at=draft.observed_at,
            freshness_window_hours=24,
            context=SignalContext(
                business_relevance=70,
                audience_relevance=70,
                urgency=50,
            ),
            confidence=draft.confidence,
            verification_status=VerificationStatus.UNVERIFIED,
            synthetic=True,
        )
        freshness = assess_freshness(
            signal, draft.freshness_category, now=self.now
        )
        authority = assess_source(
            draft.public_source,
            draft.source_category,
            stale=freshness.status
            in {FreshnessStatus.STALE, FreshnessStatus.EXPIRED},
        )
        contradictions = [
            detect_contradiction(
                EvidenceConflict(
                    claim_a=draft.claim,
                    claim_b=claim,
                    source_references=[draft.public_source],
                )
            )
            for claim in draft.contradicts_claims
        ]
        citation = Citation(
            citation_id=uuid5(NAMESPACE_URL, f"citation:{digest}"),
            evidence_id=evidence_id,
            title=draft.source_title,
            url=draft.public_source,
            publisher=draft.public_source.split("/")[2]
            if "://" in draft.public_source
            else "fixture",
            accessed_at=self.now,
        )
        score = self._score(authority, draft.confidence, freshness, contradictions)
        return CanonicalEvidence(
            evidence_id=evidence_id,
            public_source=draft.public_source,
            source_title=draft.source_title,
            source_authority=authority,
            observed_at=draft.observed_at,
            confidence=draft.confidence,
            topic=draft.topic,
            entities=draft.entities,
            claim=draft.claim,
            excerpt=draft.excerpt,
            freshness=freshness,
            contradictions=contradictions,
            provenance=draft.provenance,
            content_hash=digest,
            citation=citation,
            rank_score=score,
        )

    def _score(
        self,
        authority: SourceAuthorityAssessment,
        confidence: float,
        freshness: FreshnessAssessment,
        contradictions: list[ContradictionGroup],
    ) -> float:
        score = (
            authority.authority_score * 0.5
            + confidence * 100 * 0.3
            + self._FRESHNESS_WEIGHTS[freshness.status] * 100 * 0.2
        )
        if any(item.blocks_content_production for item in contradictions):
            score -= 35
        else:
            score -= len(contradictions) * 10
        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def _hash(draft: EvidenceDraft) -> str:
        payload = draft.model_dump(mode="json", exclude={"provenance"})
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
