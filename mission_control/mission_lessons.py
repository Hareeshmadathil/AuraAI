"""Pure deterministic mission-lesson generation from interpretations."""

from __future__ import annotations

import hashlib
import json

from pydantic import ConfigDict

from core import AuraBaseModel
from mission_control.models import (
    AnalyticsInterpretation,
    InterpretationClassification,
    InterpretationConfidence,
    LessonCategory,
    LessonConfidence,
    LessonEvidenceReference,
    LessonEvidenceState,
    LessonFinding,
    MetricEvidenceState,
)


LESSON_RULESET_VERSION = "mission-lesson-v1"
SUPPORTED_LESSON_RULESETS = frozenset({LESSON_RULESET_VERSION})


class MissionLessonPayload(AuraBaseModel):
    """Canonical deterministic lesson content without time or actor."""

    model_config = ConfigDict(frozen=True)

    analytics_interpretation_id: str
    interpretation_payload_hash: str
    lesson_ruleset_version: str
    confidence: LessonConfidence
    summary: str
    findings: tuple[LessonFinding, ...]
    evidence_references: tuple[LessonEvidenceReference, ...]
    strengths: tuple[LessonFinding, ...]
    weaknesses: tuple[LessonFinding, ...]
    unknowns: tuple[LessonFinding, ...]


def _confidence(value: InterpretationConfidence) -> LessonConfidence:
    return LessonConfidence(value.value)


def _state(value: MetricEvidenceState) -> LessonEvidenceState:
    return LessonEvidenceState(value.value)


def _reference(
    interpretation: AnalyticsInterpretation,
    metric,
) -> LessonEvidenceReference:
    return LessonEvidenceReference(
        analytics_interpretation_id=interpretation.analytics_interpretation_id,
        analytics_snapshot_id=interpretation.analytics_snapshot_id,
        metric_names=metric.source_metrics or (metric.metric_name,),
        classification=metric.classification,
        evidence_state=_state(metric.evidence_state),
        interpretation_rule_id=metric.rule_id,
    )


def _finding(
    interpretation: AnalyticsInterpretation,
    metric,
    reference: LessonEvidenceReference,
) -> LessonFinding | None:
    confidence = _confidence(metric.confidence)
    if metric.classification in {
        InterpretationClassification.STRONG,
        InterpretationClassification.OUTSTANDING,
    }:
        category = LessonCategory.PERFORMANCE_STRENGTH
        statement = (
            f"{metric.metric_name} was classified as "
            f"{metric.classification.value}."
        )
    elif metric.classification == InterpretationClassification.WEAK:
        category = LessonCategory.PERFORMANCE_WEAKNESS
        statement = f"{metric.metric_name} was classified as weak."
    elif metric.evidence_state in {
        MetricEvidenceState.MISSING,
        MetricEvidenceState.NOT_APPLICABLE,
    }:
        category = LessonCategory.EVIDENCE_GAP
        statement = (
            f"{metric.metric_name} evidence was "
            f"{metric.evidence_state.value}."
        )
    else:
        return None
    return LessonFinding(
        category=category,
        confidence=confidence,
        statement=statement,
        source_interpretation_id=interpretation.analytics_interpretation_id,
        source_metric_names=reference.metric_names,
        source_classification=metric.classification,
        source_evidence_state=reference.evidence_state,
        source_rule_ids=(metric.rule_id,),
        evidence_references=(reference,),
    )


def build_mission_lesson_payload(
    interpretation: AnalyticsInterpretation,
    *,
    lesson_ruleset_version: str = LESSON_RULESET_VERSION,
) -> MissionLessonPayload:
    """Generate stable knowledge without recalculating analytics."""

    if lesson_ruleset_version not in SUPPORTED_LESSON_RULESETS:
        raise ValueError(f"Unsupported mission lesson ruleset: {lesson_ruleset_version}")
    references = tuple(
        _reference(interpretation, metric)
        for metric in interpretation.metric_interpretations
    )
    findings = tuple(
        finding
        for metric, reference in zip(
            interpretation.metric_interpretations,
            references,
            strict=True,
        )
        if (finding := _finding(interpretation, metric, reference)) is not None
    )
    if (
        interpretation.overall_classification
        == InterpretationClassification.INSUFFICIENT_DATA
    ):
        insufficient = LessonFinding(
            category=LessonCategory.INSUFFICIENT_EVIDENCE,
            confidence=_confidence(interpretation.confidence),
            statement=(
                "The available analytics evidence was insufficient to "
                "establish an overall performance result."
            ),
            source_interpretation_id=(
                interpretation.analytics_interpretation_id
            ),
            source_metric_names=tuple(
                metric.metric_name
                for metric in interpretation.metric_interpretations
            ),
            source_classification=(
                InterpretationClassification.INSUFFICIENT_DATA
            ),
            source_evidence_state=LessonEvidenceState.MISSING,
            source_rule_ids=tuple(
                metric.rule_id
                for metric in interpretation.metric_interpretations
            ),
            evidence_references=references,
        )
        findings = (*findings, insufficient)
    strengths = tuple(
        item
        for item in findings
        if item.category == LessonCategory.PERFORMANCE_STRENGTH
    )
    weaknesses = tuple(
        item
        for item in findings
        if item.category == LessonCategory.PERFORMANCE_WEAKNESS
    )
    unknowns = tuple(
        item
        for item in findings
        if item.category in {
            LessonCategory.EVIDENCE_GAP,
            LessonCategory.INSUFFICIENT_EVIDENCE,
        }
    )
    confidence = _confidence(interpretation.confidence)
    summary = (
        f"Mission evidence established {len(strengths)} strengths, "
        f"{len(weaknesses)} weaknesses, and {len(unknowns)} unknowns "
        f"under {lesson_ruleset_version}."
    )
    return MissionLessonPayload(
        analytics_interpretation_id=str(
            interpretation.analytics_interpretation_id
        ),
        interpretation_payload_hash=interpretation.payload_hash,
        lesson_ruleset_version=lesson_ruleset_version,
        confidence=confidence,
        summary=summary,
        findings=findings,
        evidence_references=references,
        strengths=strengths,
        weaknesses=weaknesses,
        unknowns=unknowns,
    )


def mission_lesson_payload_hash(payload: MissionLessonPayload) -> str:
    """Hash canonical lesson inputs and outputs excluding actor and time."""

    encoded = json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
