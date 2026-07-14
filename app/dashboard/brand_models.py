"""Typed, deterministic read models for the local AuraAI brand review."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from core.models import AuraBaseModel


class BrandAssetStatus(StrEnum):
    """Founder-review lifecycle for a brand asset."""

    CONCEPT = "concept"


class BrandPaletteItem(AuraBaseModel):
    """One documented design-token color."""

    name: str
    token: str
    purpose: str


class LogoConceptSummary(AuraBaseModel):
    """Review-safe summary of one proposed logo family."""

    concept_id: str
    name: str
    direction: str
    rationale: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    small_size_behavior: str
    monochrome_behavior: str
    dashboard_suitability: str
    social_avatar_suitability: str
    similarity_risk: str
    review_recommendation: str
    logo_path: str
    wordmark_path: str
    app_icon_path: str
    status: BrandAssetStatus = BrandAssetStatus.CONCEPT
    review_required: bool = True


class BrandEmployeeSample(AuraBaseModel):
    """Neutral employee-component sample kept outside template markup."""

    initials: str
    name: str
    job_title: str
    department: str
    status: str


class BrandReview(AuraBaseModel):
    """Deterministic presentation data for the local brand review page."""

    brand_name: str = "AuraAI"
    descriptive_name: str = "AuraAI Media"
    positioning: str
    promise: str
    personality: list[str]
    palette: list[BrandPaletteItem]
    logo_concepts: list[LogoConceptSummary]
    employee_sample: BrandEmployeeSample
    legal_note: str


STATUS_LABELS: dict[str, str] = {
    "idle": "Idle",
    "working": "Working",
    "waiting": "Waiting",
    "paused": "Waiting",
    "blocked": "Blocked",
    "pending": "Review Required",
    "pending_approval": "Founder Approval Required",
    "approved": "Approved",
    "rejected": "Rejected",
    "revision_required": "Revision Required",
    "ready_to_render": "Ready to Render",
    "rendered": "Rendered Locally",
    "ready_to_upload": "Ready to Upload",
    "uploaded_manually": "Uploaded Manually",
    "metrics_imported": "Metrics Imported",
    "completed": "Completed",
    "failed": "Failed",
    "offline": "Offline",
    "disabled": "Disabled",
}


def status_label(value: object) -> str:
    """Return consistent user-facing copy for an internal status value."""

    raw_value = getattr(value, "value", value)
    normalized = str(raw_value).lower()
    return STATUS_LABELS.get(normalized, normalized.replace("_", " ").title())


def create_brand_review() -> BrandReview:
    """Build local, deterministic concept-review data without runtime state."""

    concepts = [
        LogoConceptSummary(
            concept_id="a",
            name="Aura Orbit",
            direction="Controlled coordination and intelligent flow.",
            rationale=(
                "An open orbital field surrounds a stable core, expressing "
                "many coordinated operations under founder control."
            ),
            strengths=["Fluid", "Distinct at dashboard scale", "Balanced"],
            risks=["Ring forms require similarity screening"],
            small_size_behavior="The core and two open arcs remain identifiable.",
            monochrome_behavior="Uses silhouette and spacing, not color effects.",
            dashboard_suitability="Strong beside the AuraAI wordmark.",
            social_avatar_suitability="Recognizable in a square field.",
            similarity_risk="Moderate; preserve the open asymmetric geometry.",
            review_recommendation="Review for coordination and calmness.",
            logo_path="/static/brand/logo-concept-a.svg",
            wordmark_path="/static/brand/wordmark-concept-a.svg",
            app_icon_path="/static/brand/app-icon-concept-a.svg",
        ),
        LogoConceptSummary(
            concept_id="b",
            name="A Monogram",
            direction="Operational paths forming upward structure.",
            rationale=(
                "Three connected paths form a proprietary abstract A without "
                "using a generic triangle or technology glyph."
            ),
            strengths=["Compact", "Structural", "Strong favicon behavior"],
            risks=["Must retain the internal path at very small sizes"],
            small_size_behavior="A broad silhouette survives at 24 pixels.",
            monochrome_behavior="Single-stroke construction stays legible.",
            dashboard_suitability="Crisp in navigation and technical contexts.",
            social_avatar_suitability="High contrast and centered.",
            similarity_risk="Low to moderate; legal screening remains required.",
            review_recommendation="Review for precision and distinctiveness.",
            logo_path="/static/brand/logo-concept-b.svg",
            wordmark_path="/static/brand/wordmark-concept-b.svg",
            app_icon_path="/static/brand/app-icon-concept-b.svg",
        ),
        LogoConceptSummary(
            concept_id="c",
            name="Signal Core",
            direction="A stable company core directing restrained movement.",
            rationale=(
                "A rounded core and offset directional rails represent one "
                "operating company coordinating specialist teams."
            ),
            strengths=["Operational", "Modular", "Clear motion hierarchy"],
            risks=["Directional geometry must not become a play-button cliché"],
            small_size_behavior="Core remains primary; rails simplify cleanly.",
            monochrome_behavior="Works as a single-color line-and-field mark.",
            dashboard_suitability="Pairs naturally with system status UI.",
            social_avatar_suitability="Strong centered core in circular crops.",
            similarity_risk="Low with the offset rail geometry retained.",
            review_recommendation="Review for operational-system meaning.",
            logo_path="/static/brand/logo-concept-c.svg",
            wordmark_path="/static/brand/wordmark-concept-c.svg",
            app_icon_path="/static/brand/app-icon-concept-c.svg",
        ),
    ]
    return BrandReview(
        positioning=(
            "The operating system for an autonomous, founder-controlled AI "
            "media company."
        ),
        promise=(
            "Make complex media operations understandable, reviewable, and "
            "controlled without overstating autonomy or outcomes."
        ),
        personality=[
            "Intelligent",
            "Calm",
            "Ambitious",
            "Precise",
            "Premium",
            "Trustworthy",
            "Creative",
            "Founder-controlled",
        ],
        palette=[
            BrandPaletteItem(
                name="Aura Aqua",
                token="--color-brand-primary",
                purpose="Identity, focus, and positive operational emphasis.",
            ),
            BrandPaletteItem(
                name="Signal Blue",
                token="--color-brand-secondary",
                purpose="Information, navigation, and data relationships.",
            ),
            BrandPaletteItem(
                name="Founder Amber",
                token="--color-founder-action",
                purpose="Approval and founder-attention states.",
            ),
            BrandPaletteItem(
                name="Deep Ink",
                token="--color-bg-canvas",
                purpose="Calm command-center foundation.",
            ),
        ],
        logo_concepts=concepts,
        employee_sample=BrandEmployeeSample(
            initials="TA",
            name="Trend Analyst",
            job_title="Intelligence specialist",
            department="intelligence",
            status="working",
        ),
        legal_note=(
            "All marks are concepts for founder review. Trademark and legal "
            "similarity screening are separate future steps."
        ),
    )
