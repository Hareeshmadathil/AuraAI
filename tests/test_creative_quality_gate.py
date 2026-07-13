from creative_quality.models import (
    CreativeQualityIssue,
    CreativeQualityScores,
    QualityDimension,
    QualityGateStatus,
    QualitySeverity,
)
from creative_quality.quality_gate import CreativeQualityGateEvaluator


def scores(overall: float) -> CreativeQualityScores:
    values = {field: overall for field in CreativeQualityScores.model_fields}
    return CreativeQualityScores(**values)


def test_gate_pass_revision_and_founder_override_states() -> None:
    evaluator = CreativeQualityGateEvaluator(75)
    assert evaluator.evaluate(scores(80), []).status == QualityGateStatus.PASSED
    assert (
        evaluator.evaluate(scores(60), []).status
        == QualityGateStatus.REVISION_REQUIRED
    )
    gate = evaluator.evaluate(scores(72), [])
    assert gate.status == QualityGateStatus.FOUNDER_OVERRIDE_REQUIRED
    assert evaluator.evaluate(
        scores(72), [], founder_override=True
    ).founder_override_used


def test_factuality_blocker_overrides_a_high_score_and_override() -> None:
    issue = CreativeQualityIssue(
        dimension=QualityDimension.FACTUALITY,
        severity=QualitySeverity.BLOCKING,
        title="Unsafe claim",
        description="Unsupported high-stakes guarantee.",
        affected_reference="claim-1",
        remediation="Remove and verify the claim.",
        blocking=True,
    )
    gate = CreativeQualityGateEvaluator().evaluate(
        scores(99), [issue], founder_override=True
    )
    assert gate.status == QualityGateStatus.BLOCKED
    assert gate.founder_override_allowed is False
