"""Offline factuality and trust-risk review."""

from __future__ import annotations

import re

from creative_quality.models import (
    FactualClaimReview,
    FactualityReport,
    QualitySeverity,
)
from production.models import ProductionPackage


class FactualityEngine:
    """Classify supplied claims and evidence without external verification."""

    _ABSOLUTE = re.compile(
        r"\b(guarantee(?:d|s)?|always|never fails?|risk[- ]free|instant income|"
        r"make \$?\d+|cure[sd]?|legally certain)\b",
        re.IGNORECASE,
    )
    _HIGH_STAKES = re.compile(
        r"\b(medical|diagnos(?:is|e)|legal advice|investment|financial advice|"
        r"income|safety critical|cure)\b",
        re.IGNORECASE,
    )

    def analyze(self, package: ProductionPackage) -> FactualityReport:
        reviews: list[FactualClaimReview] = []
        prohibited: list[str] = []
        disclaimers: set[str] = set(package.script.disclaimer_notes)
        for section in package.script.sections:
            for claim in section.claims_requiring_verification:
                evidence = bool(section.source_notes)
                absolute = bool(self._ABSOLUTE.search(claim))
                high_stakes = bool(self._HIGH_STAKES.search(claim))
                severity = (
                    QualitySeverity.BLOCKING
                    if absolute and (high_stakes or not evidence)
                    else QualitySeverity.HIGH
                    if high_stakes and not evidence
                    else QualitySeverity.MEDIUM
                    if not evidence
                    else QualitySeverity.LOW
                )
                if absolute:
                    prohibited.append(claim)
                if high_stakes:
                    disclaimers.add(
                        "High-stakes information requires expert review and a "
                        "clear disclaimer."
                    )
                reviews.append(
                    FactualClaimReview(
                        claim_text=claim,
                        section_id=section.section_id,
                        verification_required=True,
                        evidence_supplied=evidence,
                        risk_level=severity,
                        issue=(
                            "Unsupported absolute or high-stakes claim."
                            if severity
                            in {QualitySeverity.HIGH, QualitySeverity.BLOCKING}
                            else (
                                "Claim requires verification against the supplied "
                                "source notes."
                            )
                        ),
                        remediation=(
                            "Remove the guarantee, qualify the statement, and obtain "
                            "appropriate evidence or expert review."
                        ),
                        source_notes=section.source_notes,
                    )
                )
        unsupported = sum(not item.evidence_supplied for item in reviews)
        high_risk = sum(
            item.risk_level in {QualitySeverity.HIGH, QualitySeverity.BLOCKING}
            for item in reviews
        )
        score = max(0.0, 100.0 - unsupported * 12 - high_risk * 20)
        return FactualityReport(
            script_id=package.script.script_id,
            claims=reviews,
            unsupported_claim_count=unsupported,
            high_risk_claim_count=high_risk,
            disclaimer_requirements=sorted(disclaimers),
            prohibited_claims_found=prohibited,
            factuality_score=score,
            passed=high_risk == 0 and not prohibited,
        )
