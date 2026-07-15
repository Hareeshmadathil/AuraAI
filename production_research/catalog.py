"""Manually maintained placeholder catalog for offline provider research."""

from __future__ import annotations

from datetime import date

from core import ValidationError

from production_research.models import (
    PricingModel,
    ProviderCategory,
    ProviderRecord,
    ProviderStatus,
)
from production_research.scoring import ProviderScorer


class ProviderCatalog:
    """Immutable provider collection with deterministic lookup and filtering."""

    def __init__(self, providers: list[ProviderRecord]) -> None:
        names = [provider.name.casefold() for provider in providers]
        if len(names) != len(set(names)):
            raise ValidationError("Production-research provider names must be unique.")
        self._providers = tuple(ProviderScorer.rescore(item) for item in providers)

    def list_providers(
        self,
        category: ProviderCategory | None = None,
    ) -> list[ProviderRecord]:
        """Return stable score-first provider results."""

        values = (
            self._providers
            if category is None
            else tuple(item for item in self._providers if item.category == category)
        )
        return sorted(
            values,
            key=lambda item: (
                item.category.value,
                -item.local_score,
                item.name.casefold(),
            ),
        )

    def get_provider(self, name: str) -> ProviderRecord:
        """Resolve a provider name case-insensitively without fuzzy matching."""

        requested = name.strip().casefold()
        for provider in self._providers:
            if provider.name.casefold() == requested:
                return provider
        raise ValidationError(
            "Production-research provider was not found.",
            error_code="PRODUCTION_RESEARCH_PROVIDER_NOT_FOUND",
        )


def create_placeholder_catalog() -> ProviderCatalog:
    """Create explicit offline seed data for later founder-maintained research."""

    reviewed = date(2026, 7, 15)
    shared_license = (
        "Placeholder only; verify current commercial terms and asset rights "
        "before approval or production use."
    )
    definitions = [
        {
            "name": "Windows SAPI Local Voice",
            "category": ProviderCategory.VOICE,
            "website": "https://learn.microsoft.com/",
            "free_tier_available": True,
            "trial_available": False,
            "api_available": True,
            "pricing_model": PricingModel.LOCAL_LICENSE,
            "strengths": ["Offline execution", "Deterministic local access"],
            "weaknesses": ["Platform-specific voices"],
            "recommended_use_case": "Local narration prototypes and private review audio.",
            "status": ProviderStatus.APPROVED,
        },
        {
            "name": "Avatar Provider Candidate A",
            "category": ProviderCategory.AI_AVATAR,
            "website": "https://example.com/avatar-candidate",
            "free_tier_available": False,
            "trial_available": True,
            "api_available": True,
            "pricing_model": PricingModel.SUBSCRIPTION,
            "strengths": ["Candidate API workflow"],
            "weaknesses": ["Terms require review", "Output requires human review"],
            "recommended_use_case": "Founder-reviewed presenter experiments only.",
            "status": ProviderStatus.CANDIDATE,
        },
        {
            "name": "Video Generator Candidate A",
            "category": ProviderCategory.VIDEO_GENERATOR,
            "website": "https://example.com/video-candidate",
            "free_tier_available": False,
            "trial_available": True,
            "api_available": True,
            "pricing_model": PricingModel.USAGE_BASED,
            "strengths": ["Candidate scene generation"],
            "weaknesses": ["Cost requires validation", "Continuity requires review"],
            "recommended_use_case": "Optional founder-approved visual experiments.",
            "status": ProviderStatus.CANDIDATE,
        },
        {
            "name": "Thumbnail Generator Candidate A",
            "category": ProviderCategory.THUMBNAIL_GENERATOR,
            "website": "https://example.com/thumbnail-candidate",
            "free_tier_available": True,
            "trial_available": True,
            "api_available": False,
            "pricing_model": PricingModel.FREEMIUM,
            "strengths": ["Rapid concept iteration"],
            "weaknesses": ["Manual export", "Brand consistency requires review"],
            "recommended_use_case": "Non-final thumbnail concept exploration.",
            "status": ProviderStatus.CANDIDATE,
        },
        {
            "name": "Image Model Candidate A",
            "category": ProviderCategory.IMAGE_MODEL,
            "website": "https://example.com/image-candidate",
            "free_tier_available": True,
            "trial_available": False,
            "api_available": True,
            "pricing_model": PricingModel.HYBRID,
            "strengths": ["Candidate production API", "Multiple image formats"],
            "weaknesses": ["Asset rights require review"],
            "recommended_use_case": "Founder-approved supporting visual concepts.",
            "status": ProviderStatus.CANDIDATE,
        },
        {
            "name": "Script Model Candidate A",
            "category": ProviderCategory.SCRIPT_MODEL,
            "website": "https://example.com/script-candidate",
            "free_tier_available": True,
            "trial_available": False,
            "api_available": True,
            "pricing_model": PricingModel.USAGE_BASED,
            "strengths": ["Structured text candidate", "API availability"],
            "weaknesses": ["Factuality validation remains mandatory"],
            "recommended_use_case": "Typed script drafts with deterministic fallback.",
            "status": ProviderStatus.CANDIDATE,
        },
        {
            "name": "Research Model Candidate A",
            "category": ProviderCategory.RESEARCH_MODEL,
            "website": "https://example.com/research-candidate",
            "free_tier_available": True,
            "trial_available": False,
            "api_available": True,
            "pricing_model": PricingModel.USAGE_BASED,
            "strengths": ["Structured research candidate"],
            "weaknesses": ["Sources require explicit verification"],
            "recommended_use_case": "Source-bound research assistance after manual review.",
            "status": ProviderStatus.CANDIDATE,
        },
    ]
    return ProviderCatalog(
        [
            ProviderRecord(
                **definition,
                commercial_license_notes=shared_license,
                local_score=0,
                last_reviewed=reviewed,
                placeholder_data=True,
            )
            for definition in definitions
        ]
    )
