"""Local long-form MP4 assembly from deterministic scene clips."""

from __future__ import annotations

from pathlib import Path

from core import ValidationError
from production.models import ProductionPackage
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import (
    RenderArtifactType,
    RenderSettings,
    RenderedArtifact,
)
from production.rendering.validation import completed_artifact


class LocalVideoRenderer:
    """Concatenate scenes, attach local audio, and retain review labels."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner

    def render(
        self,
        *,
        package: ProductionPackage,
        scene_paths: list[Path],
        voice_path: Path | None,
        subtitle_path: Path | None,
        output_path: Path,
        settings: RenderSettings,
        founder_render_approved: bool,
        silent_fallback: bool,
    ) -> tuple[RenderedArtifact, list[str]]:
        """Produce one abridged horizontal review MP4."""

        if package.quality_report is None or not package.quality_report.passed:
            raise ValidationError("A passing Production v1 quality report is required.")
        if not founder_render_approved:
            raise ValidationError("Explicit founder render approval is required.")
        if not scene_paths:
            raise ValidationError("At least one rendered scene is required.")
        target = self.runner.require_output_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        list_path = target.with_suffix(".concat.txt")
        lines = [f"file '{self._concat_escape(path.resolve())}'" for path in scene_paths]
        list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        arguments = [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
        ]
        if voice_path is not None:
            arguments.extend(["-i", str(voice_path.resolve())])
        if settings.subtitle_burn_in and subtitle_path is not None:
            arguments.extend(["-vf", f"subtitles='{self._filter_escape(subtitle_path)}'"])
        arguments.extend(["-map", "0:v:0"])
        if voice_path is not None:
            arguments.extend(["-map", "1:a:0"])
        arguments.extend(
            [
                "-c:v",
                settings.video_codec,
                "-preset",
                "ultrafast",
                "-pix_fmt",
                settings.pixel_format,
            ]
        )
        if voice_path is not None:
            arguments.extend(
                [
                    "-c:a",
                    settings.audio_codec,
                    "-ar",
                    str(settings.audio_sample_rate),
                    "-shortest",
                ]
            )
        else:
            arguments.append("-an")
        arguments.append(str(target))
        try:
            result = self.runner.run(arguments, output_path=target)
        finally:
            if list_path.exists() and not settings.keep_intermediate_files:
                list_path.unlink()
        if not result.success:
            raise ValidationError("FFmpeg failed to assemble the long-form review pilot.")
        probe = self.runner.probe(target)
        if probe.duration_seconds > settings.maximum_render_duration_seconds + 5:
            raise ValidationError("Long-form pilot exceeds its maximum duration.")
        warnings = [
            "Abridged local rendering proof; review required and not published."
        ]
        if silent_fallback:
            warnings.append("SILENT REVIEW PREVIEW: audio contains no narration.")
        artifact = completed_artifact(
            artifact_type=RenderArtifactType.LONG_FORM_VIDEO,
            path=target,
            mime_type="video/mp4",
            sample_data=settings.sample_data,
            source_references=[f"production-package:{package.package_id}"],
            warnings=warnings,
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
        )
        return artifact, result.command_summary

    @staticmethod
    def _concat_escape(path: Path) -> str:
        return str(path).replace("\\", "/").replace("'", "'\\''")

    @staticmethod
    def _filter_escape(path: Path) -> str:
        return str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
