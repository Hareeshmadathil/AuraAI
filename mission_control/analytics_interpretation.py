"""Pure deterministic interpretation of durable analytics evidence."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from pydantic import ConfigDict

from core import AuraBaseModel
from mission_control.models import (
    AnalyticsSnapshot,
    InterpretationClassification,
    InterpretationConfidence,
    InterpretationFinding,
    MetricEvidenceState,
    MetricInterpretation,
)


RULESET_VERSION = "analytics-interpretation-v1"
SUPPORTED_RULESETS = frozenset({RULESET_VERSION})
RATIO_QUANTUM = Decimal("0.0001")

RATIO_THRESHOLDS: tuple[
    tuple[Decimal, InterpretationClassification],
    ...,
] = (
    (Decimal("0.1000"), InterpretationClassification.OUTSTANDING),
    (Decimal("0.0500"), InterpretationClassification.STRONG),
    (Decimal("0.0200"), InterpretationClassification.AVERAGE),
    (Decimal("0"), InterpretationClassification.WEAK),
)

SOURCE_METRICS = (
    "impressions",
    "views",
    "clicks",
    "likes",
    "comments",
    "shares",
    "saves",
    "watch_time_seconds",
    "followers_gained",
    "revenue_amount",
)


class InterpretationPayload(AuraBaseModel):
    """Canonical interpretation output independent of actor and wall clock."""

    model_config = ConfigDict(frozen=True)

    analytics_snapshot_id: str
    ruleset_version: str
    overall_classification: InterpretationClassification
    confidence: InterpretationConfidence
    metric_interpretations: tuple[MetricInterpretation, ...]
    strengths: tuple[InterpretationFinding, ...]
    weaknesses: tuple[InterpretationFinding, ...]
    missing_evidence: tuple[InterpretationFinding, ...]
    summary: str


def _normalized(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _source_metric(name: str, value: int | Decimal | None) -> MetricInterpretation:
    if value is None:
        state = MetricEvidenceState.MISSING
        observed = None
        normalized = None
        explanation = f"{name} evidence is missing."
    else:
        observed = Decimal(value).normalize()
        state = (
            MetricEvidenceState.ZERO
            if observed == 0
            else MetricEvidenceState.AVAILABLE
        )
        normalized = _normalized(observed)
        explanation = f"{name} evidence is {normalized}."
    return MetricInterpretation(
        metric_name=name,
        evidence_state=state,
        observed_value=observed,
        normalized_value=normalized,
        source_metrics=(name,),
        rule_id=f"{RULESET_VERSION}:source:{name}",
        classification=InterpretationClassification.INSUFFICIENT_DATA,
        confidence=InterpretationConfidence.LOW,
        explanation=explanation,
    )


def _classify_ratio(value: Decimal) -> InterpretationClassification:
    return next(
        classification
        for threshold, classification in RATIO_THRESHOLDS
        if value >= threshold
    )


def _derived_ratio(
    *,
    name: str,
    numerator: Decimal | None,
    denominator: int | None,
    source_metrics: tuple[str, ...],
    rule_suffix: str,
) -> MetricInterpretation:
    rule_id = f"{RULESET_VERSION}:{rule_suffix}"
    if numerator is None or denominator is None:
        return MetricInterpretation(
            metric_name=name,
            evidence_state=MetricEvidenceState.MISSING,
            derived=True,
            source_metrics=source_metrics,
            rule_id=rule_id,
            classification=InterpretationClassification.INSUFFICIENT_DATA,
            confidence=InterpretationConfidence.LOW,
            explanation=f"{name} cannot be calculated because required evidence is missing.",
        )
    if denominator == 0:
        return MetricInterpretation(
            metric_name=name,
            evidence_state=MetricEvidenceState.NOT_APPLICABLE,
            derived=True,
            source_metrics=source_metrics,
            rule_id=rule_id,
            classification=InterpretationClassification.INSUFFICIENT_DATA,
            confidence=InterpretationConfidence.LOW,
            explanation=f"{name} is not applicable because its denominator is zero.",
        )
    value = (numerator / Decimal(denominator)).quantize(
        RATIO_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    classification = _classify_ratio(value)
    state = MetricEvidenceState.ZERO if value == 0 else MetricEvidenceState.AVAILABLE
    return MetricInterpretation(
        metric_name=name,
        evidence_state=state,
        observed_value=value,
        normalized_value=_normalized(value),
        derived=True,
        source_metrics=source_metrics,
        rule_id=rule_id,
        classification=classification,
        confidence=InterpretationConfidence.HIGH,
        explanation=(
            f"{name} is {_normalized(value)} and is classified as "
            f"{classification.value} under {RULESET_VERSION}."
        ),
    )


def build_interpretation_payload(
    snapshot: AnalyticsSnapshot,
    *,
    ruleset_version: str = RULESET_VERSION,
) -> InterpretationPayload:
    """Return a deterministic interpretation without persistence or time."""

    if ruleset_version not in SUPPORTED_RULESETS:
        raise ValueError(f"Unsupported analytics interpretation ruleset: {ruleset_version}")

    metrics = snapshot.metrics
    source = tuple(
        _source_metric(name, getattr(metrics, name))
        for name in SOURCE_METRICS
    )
    ctr = _derived_ratio(
        name="click_through_rate",
        numerator=Decimal(metrics.clicks) if metrics.clicks is not None else None,
        denominator=metrics.impressions,
        source_metrics=("clicks", "impressions"),
        rule_suffix="ctr",
    )
    engagement_values = (
        metrics.likes,
        metrics.comments,
        metrics.shares,
        metrics.saves,
    )
    engagement_numerator = (
        sum((Decimal(value) for value in engagement_values), Decimal(0))
        if all(value is not None for value in engagement_values)
        else None
    )
    engagement = _derived_ratio(
        name="engagement_rate",
        numerator=engagement_numerator,
        denominator=metrics.views,
        source_metrics=("likes", "comments", "shares", "saves", "views"),
        rule_suffix="engagement",
    )
    interpretations = source + (ctr, engagement)
    classified = [
        item
        for item in (ctr, engagement)
        if item.classification != InterpretationClassification.INSUFFICIENT_DATA
    ]
    if classified:
        rank = {
            InterpretationClassification.WEAK: 0,
            InterpretationClassification.AVERAGE: 1,
            InterpretationClassification.STRONG: 2,
            InterpretationClassification.OUTSTANDING: 3,
        }
        inverse = {value: key for key, value in rank.items()}
        overall = inverse[
            sum(rank[item.classification] for item in classified)
            // len(classified)
        ]
        confidence = InterpretationConfidence.HIGH
    else:
        overall = InterpretationClassification.INSUFFICIENT_DATA
        available_count = sum(
            item.evidence_state in {MetricEvidenceState.AVAILABLE, MetricEvidenceState.ZERO}
            for item in source
        )
        confidence = (
            InterpretationConfidence.MEDIUM
            if available_count >= 3
            else InterpretationConfidence.LOW
        )

    strengths = tuple(
        InterpretationFinding(
            metric_names=item.source_metrics,
            rule_id=item.rule_id,
            evidence_state=item.evidence_state,
            explanation=item.explanation,
        )
        for item in classified
        if item.classification in {
            InterpretationClassification.STRONG,
            InterpretationClassification.OUTSTANDING,
        }
    )
    weaknesses = tuple(
        InterpretationFinding(
            metric_names=item.source_metrics,
            rule_id=item.rule_id,
            evidence_state=item.evidence_state,
            explanation=item.explanation,
        )
        for item in classified
        if item.classification == InterpretationClassification.WEAK
    )
    missing = tuple(
        InterpretationFinding(
            metric_names=item.source_metrics,
            rule_id=item.rule_id,
            evidence_state=item.evidence_state,
            explanation=item.explanation,
        )
        for item in interpretations
        if item.evidence_state in {
            MetricEvidenceState.MISSING,
            MetricEvidenceState.NOT_APPLICABLE,
        }
    )
    summary = (
        f"Analytics evidence is classified as {overall.value} with "
        f"{confidence.value} confidence under {ruleset_version}."
    )
    return InterpretationPayload(
        analytics_snapshot_id=str(snapshot.analytics_snapshot_id),
        ruleset_version=ruleset_version,
        overall_classification=overall,
        confidence=confidence,
        metric_interpretations=interpretations,
        strengths=strengths,
        weaknesses=weaknesses,
        missing_evidence=missing,
        summary=summary,
    )


def interpretation_payload_hash(payload: InterpretationPayload) -> str:
    """Hash canonical deterministic interpretation output and source identity."""

    encoded = json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
