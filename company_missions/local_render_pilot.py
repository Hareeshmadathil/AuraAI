"""Explicit end-to-end company mission for the local render review pilot."""

from __future__ import annotations

from pathlib import Path

from app.dashboard.service import DashboardService
from company_missions.content_production import (
    ContentProductionMission,
    create_content_production_pipeline,
)
from company_missions.fixtures import create_sample_production_input
from core import OperationResult, get_logger, utc_now
from production.models import ProductionPackage, ProductionPipelineResult
from production.rendering.models import (
    LocalRenderResult,
    RenderArtifactType,
    RenderExportManifest,
    RenderSettings,
)
from production.rendering.pipeline import build_local_render_pipeline
from production.rendering.validation import completed_artifact
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.state_manager import RuntimeStateManager


def run_local_render_pilot(
    *,
    output_root: Path,
    founder_render_approved: bool,
    overwrite: bool = False,
    keep_intermediate_files: bool = False,
    allow_silent_fallback: bool = False,
) -> OperationResult:
    """Create a deterministic v1 package and export local review media."""

    package = create_review_ready_production_package()
    settings = RenderSettings(
        output_root=output_root,
        overwrite=overwrite,
        keep_intermediate_files=keep_intermediate_files,
    )
    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    return build_local_render_pipeline(
        settings, runtime_state=state
    ).run(
        package,
        settings,
        founder_render_approved=founder_render_approved,
        allow_silent_fallback=allow_silent_fallback,
    )


def create_review_ready_production_package() -> ProductionPackage:
    """Run Production v1 using its explicit deterministic sample input."""

    pipeline, _ = create_content_production_pipeline()
    result = ContentProductionMission(pipeline).run(
        create_sample_production_input(), founder_approved=True
    )
    if not result.success:
        raise RuntimeError(result.message)
    return ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    ).package


def create_local_render_demo_dashboard_service(
    result: LocalRenderResult | None = None,
    package: ProductionPackage | None = None,
    *,
    output_root: Path | None = None,
) -> DashboardService:
    """Build the cumulative dashboard through the local render stage."""

    from app.runtime.unified_context import DashboardContextStage
    from company_missions.unified_dashboard import (
        create_unified_dashboard_service,
    )

    return create_unified_dashboard_service(
        DashboardContextStage.RENDER,
        render_result=result,
        production_package=package,
        output_root=output_root,
    )


def load_latest_local_render_demo(
    output_root: Path,
) -> tuple[LocalRenderResult, ProductionPackage] | None:
    """Load the newest valid local render manifest beneath one safe root."""

    root = output_root.resolve()
    candidates = sorted(
        root.glob("*/manifest/render-manifest.json") if root.is_dir() else (),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    logger = get_logger("company_missions.local_render_pilot")
    for path in candidates:
        try:
            manifest = RenderExportManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if manifest.settings.output_root != root:
                continue
            result = _result_from_manifest(manifest, path)
            package = create_review_ready_production_package().model_copy(
                update={"package_id": result.production_package_id}
            )
            return result, package
        except (OSError, ValueError) as error:
            logger.warning(
                "Skipped invalid local render manifest %s: %s",
                path.name,
                error.__class__.__name__,
            )
    return None


def _result_from_manifest(
    manifest: RenderExportManifest,
    manifest_path: Path,
) -> LocalRenderResult:
    """Rehydrate dashboard-safe result data from validated local files."""

    package_root = manifest_path.parent.parent
    checksum_path = package_root / "checksums" / "sha256.json"
    support = [
        completed_artifact(
            artifact_type=RenderArtifactType.RENDER_MANIFEST,
            path=manifest_path,
            mime_type="application/json",
            sample_data=manifest.settings.sample_data,
            source_references=[f"render-manifest:{manifest.manifest_id}"],
        ),
        completed_artifact(
            artifact_type=RenderArtifactType.CHECKSUM_MANIFEST,
            path=checksum_path,
            mime_type="application/json",
            sample_data=manifest.settings.sample_data,
            source_references=[f"render-manifest:{manifest.manifest_id}"],
        ),
    ]
    by_type = {
        artifact.artifact_type: artifact for artifact in manifest.artifacts
    }
    short_videos = [
        artifact
        for artifact in manifest.artifacts
        if artifact.artifact_type == RenderArtifactType.SHORT_FORM_VIDEO
    ]
    subtitles = [
        artifact
        for artifact in manifest.artifacts
        if artifact.artifact_type
        in {RenderArtifactType.SUBTITLE_SRT, RenderArtifactType.SUBTITLE_VTT}
    ]
    return LocalRenderResult(
        production_package_id=manifest.production_package_id,
        export_manifest=manifest,
        long_form_video=by_type.get(RenderArtifactType.LONG_FORM_VIDEO),
        short_form_videos=short_videos,
        thumbnail=by_type.get(RenderArtifactType.THUMBNAIL),
        voiceover=by_type.get(RenderArtifactType.VOICEOVER_AUDIO),
        subtitles=subtitles,
        exported_artifacts=[*manifest.artifacts, *support],
        runtime_snapshot=None,
        dashboard_mode="local_render_review_pilot",
        completed_at=manifest.completed_at or utc_now(),
    )


def _default_render_output_root() -> Path:
    """Return the repository-local ignored render directory."""

    return Path(__file__).resolve().parents[1] / "outputs" / "production"
