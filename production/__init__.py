"""Public interfaces for AuraAI Production Department v1."""

from production.artifact_store import ArtifactKind, ArtifactReference, ArtifactStore
from production.content_brief import ContentBriefBuilder
from production.models import (
    ApprovalRequirement,
    AssemblyTrackItem,
    AssetStatus,
    AssetType,
    ContentBrief,
    ProductionApprovalStatus,
    ProductionInput,
    ProductionPackage,
    ProductionPipelineResult,
    ProductionQualityReport,
    ProductionStage,
    ProductionStageResult,
    QualityCheck,
    QualitySeverity,
    RenderStatus,
    ScriptSection,
    ShortFormAsset,
    ShortFormPackage,
    Storyboard,
    StoryboardScene,
    SubtitlePackage,
    SubtitleSegment,
    ThumbnailConcept,
    ThumbnailPlan,
    TrackType,
    VideoAssemblyManifest,
    VideoFormat,
    VideoScript,
    VideoStyle,
    VisualAssetRequest,
    VisualGenerationPlan,
    VisualRequestKind,
    VoiceoverPlan,
    VoiceProfile,
    VoiceSegment,
)

__all__ = [
    "ApprovalRequirement", "ArtifactKind", "ArtifactReference", "ArtifactStore",
    "AssemblyTrackItem", "AssetStatus", "AssetType", "ContentBrief",
    "ContentBriefBuilder", "ProductionApprovalStatus", "ProductionInput",
    "ProductionPackage", "ProductionPipeline", "ProductionPipelineResult",
    "ProductionQualityReport", "ProductionStage", "ProductionStageResult",
    "QualityCheck", "QualitySeverity", "RenderStatus", "ScriptSection",
    "ShortFormAsset", "ShortFormPackage", "Storyboard", "StoryboardScene",
    "SubtitlePackage", "SubtitleSegment", "ThumbnailConcept", "ThumbnailPlan",
    "TrackType", "VideoAssemblyManifest", "VideoFormat", "VideoScript",
    "VideoStyle", "VisualAssetRequest", "VisualGenerationPlan", "VisualRequestKind", "VoiceoverPlan",
    "VoiceProfile", "VoiceSegment",
]


def __getattr__(name: str):
    """Load the pipeline lazily to keep employee imports cycle-free."""

    if name == "ProductionPipeline":
        from production.pipeline import ProductionPipeline

        return ProductionPipeline
    raise AttributeError(name)
