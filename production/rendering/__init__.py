"""Public interfaces for the offline Production v2 render pilot."""

from production.rendering.models import (
    LocalRenderResult,
    RenderArtifactType,
    RenderCapability,
    RenderEngine,
    RenderExportManifest,
    RenderSettings,
    RenderStageResult,
    RenderStatus,
    RenderedArtifact,
)

__all__ = [
    "LocalRenderPipeline",
    "LocalRenderResult",
    "RenderArtifactType",
    "RenderCapability",
    "RenderEngine",
    "RenderExportManifest",
    "RenderSettings",
    "RenderStageResult",
    "RenderStatus",
    "RenderedArtifact",
    "build_local_render_pipeline",
]


def __getattr__(name: str):
    """Lazily import orchestration to avoid command-line import cycles."""

    if name in {"LocalRenderPipeline", "build_local_render_pipeline"}:
        from production.rendering.pipeline import (
            LocalRenderPipeline,
            build_local_render_pipeline,
        )

        return {
            "LocalRenderPipeline": LocalRenderPipeline,
            "build_local_render_pipeline": build_local_render_pipeline,
        }[name]
    raise AttributeError(name)
