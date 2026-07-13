"""Pre-render creative-quality gate evaluation."""

from __future__ import annotations

from creative_quality.models import (
    CreativeQualityGate,
    CreativeQualityIssue,
    CreativeQualityScores,
    QualityDimension,
    QualityGateStatus,
    QualitySeverity,
)


class CreativeQualityGateEvaluator:
    """Apply explicit score and non-overridable safety rules."""

    def __init__(self, minimum_score: float = 75.0) -> None:
        if minimum_score < 0 or minimum_score > 100:
            raise ValueError("Minimum quality score must be between 0 and 100.")
        self.minimum_score = float(minimum_score)

    def evaluate(
        self,
        scores: CreativeQualityScores,
        issues: list[CreativeQualityIssue],
        *,
        founder_override: bool = False,
    ) -> CreativeQualityGate:
        """Return a gate; an override never bypasses unsafe blockers."""

        blockers = [issue for issue in issues if issue.blocking]
        unsafe = [
            issue
            for issue in blockers
            if issue.dimension
            in {QualityDimension.FACTUALITY, QualityDimension.TRUST}
            or issue.severity == QualitySeverity.BLOCKING
        ]
        warnings = [
            issue.title for issue in issues if not issue.blocking
        ]
        if blockers:
            return CreativeQualityGate(
                status=QualityGateStatus.BLOCKED,
                minimum_required_score=self.minimum_score,
                actual_score=scores.overall,
                blocking_issues=blockers,
                warnings=warnings,
                founder_override_allowed=False,
                rationale=(
                    "Unsafe factuality, trust, safety, copyright, or security "
                    "blockers require remediation before local rendering."
                    if unsafe
                    else "Blocking quality issues require remediation."
                ),
            )
        if scores.overall >= self.minimum_score:
            return CreativeQualityGate(
                status=QualityGateStatus.PASSED,
                minimum_required_score=self.minimum_score,
                actual_score=scores.overall,
                warnings=warnings,
                rationale="The internal threshold is met and no blockers exist.",
            )
        subjective_margin = self.minimum_score - scores.overall
        if subjective_margin <= 5:
            return CreativeQualityGate(
                status=(
                    QualityGateStatus.PASSED
                    if founder_override
                    else QualityGateStatus.FOUNDER_OVERRIDE_REQUIRED
                ),
                minimum_required_score=self.minimum_score,
                actual_score=scores.overall,
                warnings=warnings,
                founder_override_allowed=True,
                founder_override_used=founder_override,
                rationale=(
                    "Founder explicitly accepted low-risk subjective quality variance."
                    if founder_override
                    else (
                        "A founder decision is required for low-risk subjective "
                        "variance."
                    )
                ),
            )
        return CreativeQualityGate(
            status=QualityGateStatus.REVISION_REQUIRED,
            minimum_required_score=self.minimum_score,
            actual_score=scores.overall,
            warnings=warnings,
            rationale="One bounded deterministic revision cycle is recommended.",
        )
