"""Pure deterministic advisory recommendations from mission lessons."""
from __future__ import annotations

import hashlib
import json
from pydantic import ConfigDict
from core import AuraBaseModel
from mission_control.models import (
    LessonCategory, MissionLesson, RecommendationCategory,
    RecommendationConfidence, RecommendationEvidenceReference,
    RecommendationProposal,
)

RECOMMENDATION_RULESET_VERSION = "mission-recommendation-v1"
SUPPORTED_RECOMMENDATION_RULESETS = frozenset(
    {RECOMMENDATION_RULESET_VERSION}
)


class MissionRecommendationPayload(AuraBaseModel):
    model_config = ConfigDict(frozen=True)
    mission_lesson_id: str
    mission_lesson_payload_hash: str
    recommendation_ruleset_version: str
    confidence: RecommendationConfidence
    summary: str
    proposals: tuple[RecommendationProposal, ...]
    rationale: str
    evidence_references: tuple[RecommendationEvidenceReference, ...]


def build_mission_recommendation_payload(
    lesson: MissionLesson,
    *,
    recommendation_ruleset_version: str = RECOMMENDATION_RULESET_VERSION,
) -> MissionRecommendationPayload:
    if recommendation_ruleset_version not in SUPPORTED_RECOMMENDATION_RULESETS:
        raise ValueError("Unsupported mission recommendation ruleset.")
    proposals = []
    references = []
    for index, finding in enumerate(lesson.findings):
        if finding.category == LessonCategory.PERFORMANCE_STRENGTH:
            category = RecommendationCategory.PRESERVE_STRENGTH
            statement = "Consider preserving this supported performance pattern in a future mission."
        elif finding.category == LessonCategory.PERFORMANCE_WEAKNESS:
            category = RecommendationCategory.ADDRESS_WEAKNESS
            statement = (
                "Consider testing a different future approach related to "
                "this weak result."
            )
        elif finding.category in {LessonCategory.EVIDENCE_GAP, LessonCategory.INSUFFICIENT_EVIDENCE}:
            category = RecommendationCategory.COLLECT_MORE_EVIDENCE
            statement = "Consider collecting additional evidence before relying on this conclusion."
        else:
            continue
        rule_id = f"{recommendation_ruleset_version}:{category.value}"
        refs = tuple(
            RecommendationEvidenceReference(
                mission_lesson_id=lesson.mission_lesson_id,
                lesson_finding_index=index,
                analytics_interpretation_id=ref.analytics_interpretation_id,
                analytics_snapshot_id=ref.analytics_snapshot_id,
                source_lesson_category=finding.category,
                source_classification=ref.classification,
                source_evidence_state=ref.evidence_state,
                lesson_rule_ids=finding.source_rule_ids,
                recommendation_rule_id=rule_id,
            )
            for ref in finding.evidence_references
        )
        references.extend(refs)
        proposals.append(RecommendationProposal(
            category=category, statement=statement,
            rationale=finding.statement,
            confidence=RecommendationConfidence(finding.confidence.value),
            source_lesson_finding_indexes=(index,),
            source_lesson_categories=(finding.category,),
            source_rule_ids=(*finding.source_rule_ids, rule_id),
            limitations=("Advisory only; no causal or future outcome claim.",),
            evidence_references=refs,
        ))
    if not proposals:
        proposals.append(RecommendationProposal(
            category=RecommendationCategory.NO_ACTIONABLE_RECOMMENDATION,
            statement="No responsible future direction is supported by the current lesson.",
            rationale="The persisted lesson contains no supported actionable evidence.",
            confidence=RecommendationConfidence.LOW,
            source_lesson_finding_indexes=(),
            source_lesson_categories=(),
            source_rule_ids=(f"{recommendation_ruleset_version}:no-action",),
            limitations=("Additional evidence may change this assessment.",),
            evidence_references=(),
        ))
    confidence = RecommendationConfidence(lesson.confidence.value)
    summary = f"{len(proposals)} advisory proposal(s) derived under {recommendation_ruleset_version}."
    return MissionRecommendationPayload(
        mission_lesson_id=str(lesson.mission_lesson_id),
        mission_lesson_payload_hash=lesson.payload_hash,
        recommendation_ruleset_version=recommendation_ruleset_version,
        confidence=confidence, summary=summary, proposals=tuple(proposals),
        rationale="Proposals are limited to persisted mission-lesson findings.",
        evidence_references=tuple(references),
    )


def mission_recommendation_payload_hash(
    payload: MissionRecommendationPayload,
) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()
