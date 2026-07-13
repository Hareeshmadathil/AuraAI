"""Truthful deterministic thumbnail concept scoring."""

from __future__ import annotations

from creative_quality.models import ThumbnailConceptScore, ThumbnailQualityReport
from production.models import ThumbnailConcept, ThumbnailPlan


class ThumbnailQualityEngine:
    """Compare supplied concepts without claiming click-through prediction."""

    _MISLEADING = ("guaranteed", "instant", "secret", "get rich", "100%")

    def analyze(self, plan: ThumbnailPlan) -> ThumbnailQualityReport:
        scores = [self._score(concept) for concept in plan.concepts]
        recommended = max(scores, key=lambda item: item.total_score)
        return ThumbnailQualityReport(
            thumbnail_plan_id=plan.plan_id,
            concepts=scores,
            recommended_concept_id=recommended.concept_id,
            recommendation_reason=(
                "Highest internal balance of clarity, truthful curiosity, contrast, "
                "trust, mobile readability, and topic alignment."
            ),
            ab_test_hypothesis=(
                "Compare concise problem-led text with a no-text evidence-led variant; "
                "measure actual performance after human approval."
            ),
        )

    def _score(self, concept: ThumbnailConcept) -> ThumbnailConceptScore:
        text = f"{concept.primary_text} {concept.secondary_text or ''}".strip()
        lowered = f"{text} {concept.emotional_trigger}".lower()
        clickbait = 85 if any(term in lowered for term in self._MISLEADING) else 12
        mobile = 92 if len(text) <= 32 else (72 if len(text) <= 48 else 52)
        clarity = 90 if len(concept.primary_text.split()) <= 6 else 68
        trust = 45 if clickbait > 50 else 88
        curiosity = 72 if clickbait > 50 else 84
        contrast = 86 if concept.contrast_guidance else 65
        emotion = 78
        alignment = 88
        total = (
            clarity * 0.18
            + curiosity * 0.16
            + contrast * 0.12
            + emotion * 0.10
            + trust * 0.18
            + mobile * 0.14
            + alignment * 0.12
            - clickbait * 0.12
        )
        weaknesses = []
        recommendations = []
        if clickbait > 50:
            weaknesses.append("The concept implies a misleading or guaranteed outcome.")
            recommendations.append(
                "Replace the claim with a truthful, specific contrast."
            )
        if mobile < 70:
            weaknesses.append("The text is difficult to scan on a small screen.")
            recommendations.append("Reduce the primary text to six words or fewer.")
        return ThumbnailConceptScore(
            concept_id=concept.concept_id,
            clarity_score=clarity,
            curiosity_score=curiosity,
            contrast_score=contrast,
            emotional_score=emotion,
            trust_score=trust,
            mobile_readability_score=mobile,
            topic_alignment_score=alignment,
            clickbait_risk=clickbait,
            total_score=round(max(0, min(100, total)), 2),
            weaknesses=weaknesses,
            recommendations=recommendations,
        )
