"""Safe, explicit entry point for AuraAI's local render review pilot."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from core import OperationResult
from creative_quality.models import CreativeQualityPackage, QualityGateStatus
from production.models import ProductionPackage, ProductionPipelineResult
from production.rendering.capabilities import RenderCapabilityDetector
from production.rendering.export_service import RenderExportService
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import (
    LocalRenderResult,
    RenderCapability,
    RenderSettings,
    RenderStageResult,
)
from production.rendering.scene_renderer import DeterministicSceneRenderer
from production.rendering.short_renderer import LocalShortRenderer
from production.rendering.subtitle_renderer import SubtitleFileExporter
from production.rendering.thumbnail_renderer import LocalThumbnailRenderer
from production.rendering.validation import RenderValidator
from production.rendering.video_renderer import LocalVideoRenderer
from production.rendering.voice_renderer import OfflineVoiceRenderer
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventSeverity, RuntimeEventType
from runtime_engine.state_manager import RuntimeStateManager


class LocalRenderPipeline:
    """Coordinate capability checks, approval, export, and runtime events."""

    _STAGE_EVENTS = {
        "voice_render": RuntimeEventType.VOICE_RENDER_COMPLETED,
        "subtitle_export": RuntimeEventType.SUBTITLE_EXPORT_COMPLETED,
        "scene_render": RuntimeEventType.SCENE_RENDER_COMPLETED,
        "thumbnail_render": RuntimeEventType.THUMBNAIL_RENDER_COMPLETED,
        "long_form_render": RuntimeEventType.LONG_FORM_RENDER_COMPLETED,
        "short_render": RuntimeEventType.SHORT_RENDER_COMPLETED,
        "render_validation": RuntimeEventType.RENDER_VALIDATION_COMPLETED,
    }

    def __init__(
        self,
        *,
        capability_detector: RenderCapabilityDetector,
        export_service: RenderExportService,
        runtime_state: RuntimeStateManager | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.capability_detector = capability_detector
        self.export_service = export_service
        self.runtime_state = runtime_state
        self.event_bus = event_bus or (
            runtime_state.event_bus if runtime_state is not None else None
        )

    def run(
        self,
        package: ProductionPackage,
        settings: RenderSettings,
        *,
        founder_render_approved: bool = False,
        allow_silent_fallback: bool = False,
        creative_quality_package: CreativeQualityPackage | None = None,
        quality_enforcement_enabled: bool = False,
        founder_quality_override: bool = False,
    ) -> OperationResult:
        """Execute a bounded local render; never publish its artifacts."""

        self._emit(RuntimeEventType.RENDER_REQUESTED, "Local render requested.")
        quality_failure = self._validate_quality_gate(
            package,
            creative_quality_package,
            enforcement_enabled=quality_enforcement_enabled,
            founder_quality_override=founder_quality_override,
        )
        if quality_failure is not None:
            return quality_failure
        if not founder_render_approved:
            self._emit(
                RuntimeEventType.FOUNDER_REVIEW_REQUIRED,
                "Founder render approval is required before local rendering.",
                severity=RuntimeEventSeverity.WARNING,
            )
            return OperationResult.failure(
                "Founder render approval is required.",
                error_code="FOUNDER_RENDER_APPROVAL_REQUIRED",
            )

        capabilities = self.capability_detector.detect()
        self._emit(
            RuntimeEventType.CAPABILITY_CHECK_COMPLETED,
            "Local rendering capabilities checked.",
            metadata={
                item.capability_name: item.available for item in capabilities
            },
        )
        missing = self._missing_required_capabilities(capabilities)
        if missing:
            message = (
                "Required local render capabilities unavailable: "
                + ", ".join(missing)
            )
            self._emit(
                RuntimeEventType.RENDER_FAILED,
                message,
                severity=RuntimeEventSeverity.ERROR,
            )
            return OperationResult.failure(
                message,
                error_code="LOCAL_RENDER_CAPABILITY_UNAVAILABLE",
                data={
                    "capabilities": [
                        item.model_dump(mode="json") for item in capabilities
                    ]
                },
            )

        self._emit(RuntimeEventType.RENDER_STARTED, "Local render started.")
        result = self.export_service.export(
            package,
            settings,
            capabilities,
            founder_render_approved=True,
            allow_silent_fallback=allow_silent_fallback,
            stage_callback=self._record_stage,
        )
        if not result.success:
            self._emit(
                RuntimeEventType.RENDER_FAILED,
                result.message,
                severity=RuntimeEventSeverity.ERROR,
            )
            return result

        local_result = LocalRenderResult.model_validate(
            result.data["local_render_result"]
        )
        if self.runtime_state is not None:
            state = self.runtime_state.register_render_result(
                local_result,
                replace=True,
            )
            local_result.runtime_snapshot = state.model_dump(mode="json")
            result.data["local_render_result"] = local_result.model_dump(mode="json")
        self._emit(RuntimeEventType.RENDER_COMPLETED, "Local render completed.")
        self._emit(
            RuntimeEventType.FOUNDER_REVIEW_REQUIRED,
            "Rendered artifacts require founder review and are not published.",
        )
        return result

    @staticmethod
    def _validate_quality_gate(
        package: ProductionPackage,
        quality: CreativeQualityPackage | None,
        *,
        enforcement_enabled: bool,
        founder_quality_override: bool,
    ) -> OperationResult | None:
        """Enforce optional quality approval separately from render approval."""

        if not enforcement_enabled:
            return None
        if quality is None:
            return OperationResult.failure(
                "Creative Quality review is required before local rendering.",
                error_code="CREATIVE_QUALITY_REQUIRED",
            )
        if quality.production_package_id != package.package_id:
            return OperationResult.failure(
                "Creative Quality package does not match the production package.",
                error_code="CREATIVE_QUALITY_PACKAGE_MISMATCH",
            )
        gate = quality.gate
        if gate.status == QualityGateStatus.BLOCKED:
            return OperationResult.failure(
                "Creative Quality blockers must be resolved before rendering.",
                error_code="CREATIVE_QUALITY_BLOCKED",
            )
        if gate.status == QualityGateStatus.REVISION_REQUIRED:
            return OperationResult.failure(
                "Creative Quality revisions require review before rendering.",
                error_code="CREATIVE_QUALITY_REVISION_REQUIRED",
            )
        if gate.status == QualityGateStatus.FOUNDER_OVERRIDE_REQUIRED:
            if not founder_quality_override or not gate.founder_override_allowed:
                return OperationResult.failure(
                    "Explicit founder quality override is required.",
                    error_code="FOUNDER_QUALITY_OVERRIDE_REQUIRED",
                )
        return None

    def _record_stage(self, stage: RenderStageResult) -> None:
        event_type = self._STAGE_EVENTS.get(stage.stage_name)
        if event_type is not None:
            self._emit(
                event_type,
                f"Local render stage completed: {stage.stage_name}.",
                severity=(
                    RuntimeEventSeverity.INFO
                    if stage.success
                    else RuntimeEventSeverity.ERROR
                ),
            )

    def _emit(
        self,
        event_type: RuntimeEventType,
        message: str,
        *,
        severity: RuntimeEventSeverity = RuntimeEventSeverity.INFO,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(
                event_type,
                message,
                severity=severity,
                metadata=metadata or {},
            )

    @staticmethod
    def _missing_required_capabilities(
        capabilities: Sequence[RenderCapability],
    ) -> list[str]:
        values = {item.capability_name: item.available for item in capabilities}
        return [name for name in ("ffmpeg", "ffprobe") if not values.get(name, False)]


def build_local_render_pipeline(
    settings: RenderSettings,
    *,
    runtime_state: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> LocalRenderPipeline:
    """Build an isolated pipeline without performing capability checks."""

    detector = RenderCapabilityDetector()
    paths = detector.locate_executables()
    runner = FFmpegRunner(
        ffmpeg_path=paths.get("ffmpeg") or "ffmpeg",
        ffprobe_path=paths.get("ffprobe") or "ffprobe",
        output_root=settings.output_root,
    )
    service = RenderExportService(
        voice_renderer=OfflineVoiceRenderer(output_root=settings.output_root),
        scene_renderer=DeterministicSceneRenderer(runner),
        thumbnail_renderer=LocalThumbnailRenderer(runner),
        subtitle_exporter=SubtitleFileExporter(settings.output_root),
        video_renderer=LocalVideoRenderer(runner),
        short_renderer=LocalShortRenderer(runner),
        validator=RenderValidator(runner),
    )
    return LocalRenderPipeline(
        capability_detector=detector,
        export_service=service,
        runtime_state=runtime_state,
        event_bus=event_bus,
    )


def _demo_package() -> ProductionPackage:
    from company_missions import (
        ContentProductionMission,
        create_content_production_pipeline,
        create_sample_production_input,
    )

    production_pipeline, _ = create_content_production_pipeline()
    result = ContentProductionMission(production_pipeline).run(
        create_sample_production_input(), founder_approved=True
    )
    if not result.success:
        raise RuntimeError(result.message)
    return ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    ).package


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the explicit deterministic local demo from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--founder-render-approved", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/production"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-intermediates", action="store_true")
    parser.add_argument("--silent-fallback", action="store_true")
    values = parser.parse_args(arguments)
    if not values.demo:
        parser.error("Only the explicit --demo pilot is supported.")
    settings = RenderSettings(
        output_root=values.output_root,
        overwrite=values.overwrite,
        keep_intermediate_files=values.keep_intermediates,
    )
    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    pipeline = build_local_render_pipeline(settings, runtime_state=state)
    result = pipeline.run(
        _demo_package(),
        settings,
        founder_render_approved=values.founder_render_approved,
        allow_silent_fallback=values.silent_fallback,
    )
    print(result.model_dump_json(indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
