"""Founder-controlled local distribution preparation."""

from typing import Any

from distribution.models import (
    ApprovalChange,
    ChapterMarker,
    DistributionChannel,
    DistributionPackage,
    DistributionPlan,
    DistributionTaskAssignment,
    ManualApprovalChecklist,
    MetadataPackage,
    PlatformDistributionPackage,
    PublishChecklistItem,
    PublishingState,
    ThumbnailDistributionPackage,
    UploadInstruction,
)


def __getattr__(name: str) -> Any:
    """Load service types lazily to keep domain models import-safe."""

    if name == "DistributionApprovalService":
        from distribution.approval import DistributionApprovalService

        return DistributionApprovalService
    if name in {"DistributionPipeline", "create_distribution_pipeline"}:
        from distribution.pipeline import (
            DistributionPipeline,
            create_distribution_pipeline,
        )

        return {
            "DistributionPipeline": DistributionPipeline,
            "create_distribution_pipeline": create_distribution_pipeline,
        }[name]
    raise AttributeError(name)


__all__ = [
    "ApprovalChange",
    "ChapterMarker",
    "DistributionApprovalService",
    "DistributionChannel",
    "DistributionPackage",
    "DistributionPipeline",
    "DistributionPlan",
    "DistributionTaskAssignment",
    "ManualApprovalChecklist",
    "MetadataPackage",
    "PlatformDistributionPackage",
    "PublishChecklistItem",
    "PublishingState",
    "ThumbnailDistributionPackage",
    "UploadInstruction",
    "create_distribution_pipeline",
]
