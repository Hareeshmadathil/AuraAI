"""Explicit local render/export orchestration and manifest persistence."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import OperationResult, ValidationError, utc_now
from production.models import ProductionPackage
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
from production.rendering.scene_renderer import DeterministicSceneRenderer
from production.rendering.short_renderer import LocalShortRenderer
from production.rendering.subtitle_renderer import SubtitleFileExporter
from production.rendering.thumbnail_renderer import LocalThumbnailRenderer
from production.rendering.validation import (
    RenderValidator,
    completed_artifact,
    sha256_file,
)
from production.rendering.video_renderer import LocalVideoRenderer
from production.rendering.voice_renderer import OfflineVoiceRenderer


class RenderExportService:
    """Create an isolated, never-published local export for one package."""

    def __init__(
        self,
        *,
        voice_renderer: OfflineVoiceRenderer,
        scene_renderer: DeterministicSceneRenderer,
        thumbnail_renderer: LocalThumbnailRenderer,
        subtitle_exporter: SubtitleFileExporter,
        video_renderer: LocalVideoRenderer,
        short_renderer: LocalShortRenderer,
        validator: RenderValidator,
    ) -> None:
        self.voice_renderer = voice_renderer
        self.scene_renderer = scene_renderer
        self.thumbnail_renderer = thumbnail_renderer
        self.subtitle_exporter = subtitle_exporter
        self.video_renderer = video_renderer
        self.short_renderer = short_renderer
        self.validator = validator

    def export(
        self,
        package: ProductionPackage,
        settings: RenderSettings,
        capabilities: list[RenderCapability],
        *,
        founder_render_approved: bool,
        allow_silent_fallback: bool,
        stage_callback: Callable[[RenderStageResult], None] | None = None,
    ) -> OperationResult:
        """Render all pilot outputs and preserve partial metadata on failure."""

        root = settings.output_root / str(package.package_id)
        stages: list[RenderStageResult] = []
        artifacts: list[RenderedArtifact] = []
        directories = self._prepare_directories(root, settings)
        try:
            sapi = self._capability(capabilities, "windows_sapi")
            started = utc_now()
            voice = self.voice_renderer.render(
                package.voiceover_plan,
                directories["audio"] / "voiceover.wav",
                sapi,
                allow_silent_fallback=allow_silent_fallback,
                maximum_duration_seconds=settings.maximum_render_duration_seconds,
            )
            voice_stage = RenderStageResult(
                stage_name="voice_render",
                success=voice.artifact is not None,
                status=voice.status,
                started_at=started,
                completed_at=utc_now(),
                command_summary=voice.command_summary,
                artifacts=[voice.artifact] if voice.artifact else [],
                warnings=voice.warnings,
                error_message=None if voice.artifact else voice.message,
            )
            self._record(voice_stage, stages, stage_callback)
            if voice.artifact is None:
                return self._failure(voice.message, stages, artifacts, root)
            artifacts.append(voice.artifact)
            silent = voice.engine == RenderEngine.SILENT_FALLBACK

            started = utc_now()
            subtitles = self.subtitle_exporter.export(
                package.subtitle_package,
                directories["subtitles"],
                settings,
            )
            artifacts.extend(subtitles)
            self._record(
                RenderStageResult(
                    stage_name="subtitle_export",
                    success=True,
                    status=RenderStatus.REVIEW_REQUIRED,
                    started_at=started,
                    completed_at=utc_now(),
                    artifacts=subtitles,
                ),
                stages,
                stage_callback,
            )

            started = utc_now()
            scene_artifacts, scene_commands = self._render_scenes(
                package, directories["scenes"], settings, silent
            )
            self._record(
                RenderStageResult(
                    stage_name="scene_render",
                    success=True,
                    status=RenderStatus.REVIEW_REQUIRED,
                    started_at=started,
                    completed_at=utc_now(),
                    command_summary=scene_commands,
                    artifacts=scene_artifacts,
                    warnings=["Scene cards are local visualization placeholders."],
                ),
                stages,
                stage_callback,
            )

            started = utc_now()
            thumbnail, thumbnail_command = self.thumbnail_renderer.render(
                package.thumbnail_plan,
                directories["thumbnails"] / "thumbnail.png",
                settings,
            )
            artifacts.append(thumbnail)
            self._record(
                RenderStageResult(
                    stage_name="thumbnail_render",
                    success=True,
                    status=RenderStatus.REVIEW_REQUIRED,
                    started_at=started,
                    completed_at=utc_now(),
                    command_summary=thumbnail_command,
                    artifacts=[thumbnail],
                ),
                stages,
                stage_callback,
            )

            started = utc_now()
            long_video, long_command = self.video_renderer.render(
                package=package,
                scene_paths=[artifact.path for artifact in scene_artifacts],
                voice_path=voice.artifact.path,
                subtitle_path=subtitles[0].path,
                output_path=directories["videos"] / "long-form-review.mp4",
                settings=settings,
                founder_render_approved=founder_render_approved,
                silent_fallback=silent,
            )
            artifacts.append(long_video)
            self._record(
                RenderStageResult(
                    stage_name="long_form_render",
                    success=True,
                    status=RenderStatus.REVIEW_REQUIRED,
                    started_at=started,
                    completed_at=utc_now(),
                    command_summary=long_command,
                    artifacts=[long_video],
                    warnings=list(long_video.warnings),
                ),
                stages,
                stage_callback,
            )

            started = utc_now()
            short_video, short_command = self.short_renderer.render(
                asset=package.short_form_package.assets[0],
                output_path=directories["shorts"] / "vertical-review.mp4",
                settings=settings,
                voice_path=voice.artifact.path,
                silent_fallback=silent,
                duration_seconds=min(20, settings.maximum_render_duration_seconds),
            )
            artifacts.append(short_video)
            self._record(
                RenderStageResult(
                    stage_name="short_render",
                    success=True,
                    status=RenderStatus.REVIEW_REQUIRED,
                    started_at=started,
                    completed_at=utc_now(),
                    command_summary=short_command,
                    artifacts=[short_video],
                    warnings=list(short_video.warnings),
                ),
                stages,
                stage_callback,
            )

            manifest = RenderExportManifest(
                production_package_id=package.package_id,
                render_engine=RenderEngine.FFMPEG,
                settings=settings,
                capabilities=capabilities,
                artifacts=list(artifacts),
                stage_results=stages,
                overall_status=RenderStatus.REVIEW_REQUIRED,
                review_required=True,
                publish_allowed=False,
                warnings=[
                    "LOCAL REVIEW PILOT: deterministic, review required, not published.",
                    "The long-form video is an abridged rendering proof.",
                    *(voice.warnings),
                ],
                completed_at=utc_now(),
            )
            started = utc_now()
            report = self.validator.validate(manifest)
            validation_stage = RenderStageResult(
                stage_name="render_validation",
                success=report.passed,
                status=(
                    RenderStatus.REVIEW_REQUIRED if report.passed else RenderStatus.FAILED
                ),
                started_at=started,
                completed_at=utc_now(),
                warnings=report.warnings,
                error_message=None if report.passed else "; ".join(report.blockers),
            )
            self._record(validation_stage, stages, stage_callback)
            manifest.stage_results = stages
            if not report.passed:
                manifest.overall_status = RenderStatus.FAILED
                return self._failure(
                    "Local render validation failed.", stages, artifacts, root,
                    manifest=manifest,
                )

            if not settings.keep_intermediate_files:
                for artifact in scene_artifacts:
                    artifact.path.unlink(missing_ok=True)
                scene_stage = next(
                    stage for stage in stages if stage.stage_name == "scene_render"
                )
                scene_stage.artifacts = []
                scene_stage.warnings.append(
                    "Intermediate scene clips were removed after successful assembly."
                )
            manifest.stage_results = stages
            support_artifacts = self._write_manifests(
                manifest, directories, settings
            )
            exported = [*artifacts, *support_artifacts]
            result = LocalRenderResult(
                production_package_id=package.package_id,
                export_manifest=manifest,
                long_form_video=long_video,
                short_form_videos=[short_video],
                thumbnail=thumbnail,
                voiceover=voice.artifact,
                subtitles=subtitles,
                exported_artifacts=exported,
                runtime_snapshot=None,
                dashboard_mode="local_render_review_pilot",
                completed_at=utc_now(),
            )
            return OperationResult.ok(
                "Local render pilot completed; review required and nothing published.",
                data={"local_render_result": result.model_dump(mode="json")},
            )
        except Exception as error:
            stage = RenderStageResult(
                stage_name="render_export",
                success=False,
                status=RenderStatus.FAILED,
                started_at=utc_now(),
                completed_at=utc_now(),
                artifacts=[],
                error_message=f"{error.__class__.__name__}: {error}",
            )
            self._record(stage, stages, stage_callback)
            return self._failure(
                "Local render export failed safely.", stages, artifacts, root
            )

    @staticmethod
    def _prepare_directories(
        root: Path,
        settings: RenderSettings,
    ) -> dict[str, Path]:
        if root.exists() and any(root.iterdir()) and not settings.overwrite:
            raise ValidationError("Render package output already exists.")
        names = (
            "manifest", "audio", "scenes", "subtitles", "thumbnails",
            "videos", "shorts", "checksums",
        )
        directories = {name: root / name for name in names}
        for directory in directories.values():
            directory.mkdir(parents=True, exist_ok=True)
        return directories

    def _render_scenes(
        self,
        package: ProductionPackage,
        directory: Path,
        settings: RenderSettings,
        silent: bool,
    ) -> tuple[list[RenderedArtifact], list[str]]:
        scenes = package.storyboard.scenes
        card_duration = 2.0
        content_duration = max(
            5.0,
            settings.maximum_render_duration_seconds - card_duration * 2,
        )
        source_total = sum(scene.end_seconds - scene.start_seconds for scene in scenes)
        durations = [
            max(0.75, content_duration * (scene.end_seconds - scene.start_seconds) / source_total)
            for scene in scenes
        ]
        intro = scenes[0].model_copy(
            update={"on_screen_text": "AuraAI Local Review Pilot"}
        )
        outro = scenes[-1].model_copy(
            update={"on_screen_text": "Review Required - Not Published"}
        )
        render_values = [(intro, card_duration), *zip(scenes, durations), (outro, card_duration)]
        artifacts: list[RenderedArtifact] = []
        commands: list[str] = []
        total = len(render_values)
        for index, (scene, duration) in enumerate(render_values, start=1):
            artifact, command = self.scene_renderer.render(
                scene,
                directory / f"scene-{index:02d}.mp4",
                settings,
                duration_seconds=duration,
                scene_index=index,
                scene_count=total,
                silent_preview=silent,
            )
            artifacts.append(artifact)
            commands.extend(command)
        return artifacts, commands

    @staticmethod
    def _write_manifests(
        manifest: RenderExportManifest,
        directories: dict[str, Path],
        settings: RenderSettings,
    ) -> list[RenderedArtifact]:
        manifest_path = directories["manifest"] / "render-manifest.json"
        if manifest_path.exists() and not settings.overwrite:
            raise ValidationError("Render manifest already exists.")
        manifest_path.write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        manifest_artifact = completed_artifact(
            artifact_type=RenderArtifactType.RENDER_MANIFEST,
            path=manifest_path,
            mime_type="application/json",
            sample_data=settings.sample_data,
            source_references=[f"render-manifest:{manifest.manifest_id}"],
        )
        checksum_path = directories["checksums"] / "sha256.json"
        checksum_values = {
            str(artifact.artifact_id): {
                "path": str(artifact.path.relative_to(settings.output_root)),
                "sha256": artifact.checksum_sha256,
            }
            for artifact in [*manifest.artifacts, manifest_artifact]
        }
        checksum_path.write_text(
            json.dumps(checksum_values, indent=2, sort_keys=True), encoding="utf-8"
        )
        checksum_artifact = completed_artifact(
            artifact_type=RenderArtifactType.CHECKSUM_MANIFEST,
            path=checksum_path,
            mime_type="application/json",
            sample_data=settings.sample_data,
            source_references=[f"render-manifest:{manifest.manifest_id}"],
        )
        return [manifest_artifact, checksum_artifact]

    @staticmethod
    def _capability(
        capabilities: list[RenderCapability], name: str
    ) -> RenderCapability:
        return next(
            (
                capability
                for capability in capabilities
                if capability.capability_name == name
            ),
            RenderCapability(
                capability_name=name,
                available=False,
                message=f"{name} capability was not supplied.",
            ),
        )

    @staticmethod
    def _record(
        stage: RenderStageResult,
        stages: list[RenderStageResult],
        callback: Callable[[RenderStageResult], None] | None,
    ) -> None:
        stages.append(stage)
        if callback is not None:
            callback(stage)

    @staticmethod
    def _failure(
        message: str,
        stages: list[RenderStageResult],
        artifacts: list[RenderedArtifact],
        root: Path,
        *,
        manifest: RenderExportManifest | None = None,
    ) -> OperationResult:
        return OperationResult.failure(
            message,
            error_code="LOCAL_RENDER_EXPORT_FAILED",
            data={
                "stage_results": [stage.model_dump(mode="json") for stage in stages],
                "partial_artifacts": [
                    artifact.model_dump(mode="json") for artifact in artifacts
                ],
                "output_directory": str(root),
                "export_manifest": (
                    manifest.model_dump(mode="json") if manifest else None
                ),
            },
        )
