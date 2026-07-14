"""Public API for AuraAI Real Content Pilot v1."""

from company_missions.real_content_pilot.artifacts import (
    CreativeQualityArtifact,
    FounderReviewArtifact,
    FounderReviewStatus,
    ResearchArtifact,
    SEOArtifact,
    ScriptArtifact,
)
from company_missions.real_content_pilot.fixtures import (
    create_sample_real_content_pilot_input,
    run_deterministic_real_content_pilot,
)
from company_missions.real_content_pilot.inputs import RealContentPilotInput
from company_missions.real_content_pilot.models import (
    PilotStageResult,
    PilotStageStatus,
    ProviderStageUsage,
    RealContentPilotResult,
)
from company_missions.real_content_pilot.pipeline import (
    FounderReviewService,
    RealContentPilot,
    TypedPilotArtifactStore,
    create_founder_controlled_live_pilot,
)


def create_real_content_pilot_demo_dashboard_service():
    """Import the dashboard adapter lazily to avoid application cycles."""

    from company_missions.real_content_pilot.dashboard import (
        create_real_content_pilot_demo_dashboard_service as create_service,
    )

    return create_service()

__all__ = [
    "CreativeQualityArtifact",
    "FounderReviewArtifact",
    "FounderReviewService",
    "FounderReviewStatus",
    "PilotStageResult",
    "PilotStageStatus",
    "ProviderStageUsage",
    "RealContentPilot",
    "RealContentPilotInput",
    "RealContentPilotResult",
    "ResearchArtifact",
    "SEOArtifact",
    "ScriptArtifact",
    "TypedPilotArtifactStore",
    "create_founder_controlled_live_pilot",
    "create_real_content_pilot_demo_dashboard_service",
    "create_sample_real_content_pilot_input",
    "run_deterministic_real_content_pilot",
]
