"""Transparent deterministic scoring for production-provider candidates."""

from __future__ import annotations

from production_research.models import PricingModel, ProviderRecord


class ProviderScorer:
    """Score required provider fields with a fixed, inspectable formula."""

    METHODOLOGY = (
        "Score = 30 baseline + 20 API availability + 10 free tier + 5 trial "
        "+ 10 documented commercial terms + 5 known pricing model + up to "
        "20 strength points - up to 20 weakness points. Scores are local "
        "comparison heuristics, not provider performance guarantees."
    )

    @classmethod
    def score_fields(
        cls,
        *,
        api_available: bool,
        free_tier_available: bool,
        trial_available: bool,
        commercial_license_notes: str,
        pricing_model: PricingModel,
        strengths: list[str],
        weaknesses: list[str],
    ) -> int:
        """Return the same bounded score for the same supplied metadata."""

        score = 30
        score += 20 if api_available else 0
        score += 10 if free_tier_available else 0
        score += 5 if trial_available else 0
        score += 10 if commercial_license_notes.strip() else 0
        score += 5 if pricing_model != PricingModel.UNKNOWN else 0
        score += min(len(strengths) * 5, 20)
        score -= min(len(weaknesses) * 5, 20)
        return max(0, min(100, score))

    @classmethod
    def rescore(cls, provider: ProviderRecord) -> ProviderRecord:
        """Return a provider copy with its deterministic local score updated."""

        return provider.model_copy(
            update={
                "local_score": cls.score_fields(
                    api_available=provider.api_available,
                    free_tier_available=provider.free_tier_available,
                    trial_available=provider.trial_available,
                    commercial_license_notes=provider.commercial_license_notes,
                    pricing_model=provider.pricing_model,
                    strengths=provider.strengths,
                    weaknesses=provider.weaknesses,
                )
            }
        )
