"""Deterministic FFmpeg scene cards for local visualization review."""

from __future__ import annotations

import re
from pathlib import Path

from core import ValidationError
from production.models import StoryboardScene, VideoStyle
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.graphics import drawtext_filter
from production.rendering.models import RenderArtifactType, RenderSettings, RenderedArtifact
from production.rendering.validation import completed_artifact


class DeterministicSceneRenderer:
    """Render neutral motion-graphic scene clips without external assets."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner

    def render(
        self,
        scene: StoryboardScene,
        output_path: Path,
        settings: RenderSettings,
        *,
        duration_seconds: float,
        scene_index: int,
        scene_count: int,
        silent_preview: bool = False,
        vertical: bool = False,
    ) -> tuple[RenderedArtifact, list[str]]:
        """Create one real MP4 information card."""

        width = settings.short_width if vertical else settings.long_form_width
        height = settings.short_height if vertical else settings.long_form_height
        target = self.runner.require_output_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        heading = self._safe_text(scene.on_screen_text or f"Scene {scene_index}")
        placeholder = self._placeholder_label(scene.style)
        progress = f"{scene_index} / {scene_count}"
        filters = [
            "drawbox=x=0:y=0:w=iw:h=ih:color=0x08111f:t=fill",
            "drawbox=x=0:y=0:w=iw:h=12:color=0x62e6c5:t=fill",
            (
                f"{drawtext_filter('LOCAL REVIEW PILOT')}:fontcolor=0x62e6c5:"
                f"fontsize={max(20, width // 45)}:x={width * 0.06}:y={height * 0.08}"
            ),
            (
                f"{drawtext_filter(heading)}:fontcolor=white:"
                f"fontsize={max(30, width // 24)}:x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            (
                f"{drawtext_filter(placeholder)}:fontcolor=0x9caac2:"
                f"fontsize={max(18, width // 55)}:x=(w-text_w)/2:y={height * 0.68}"
            ),
            (
                f"{drawtext_filter(progress)}:fontcolor=0x79a8ff:"
                f"fontsize={max(16, width // 65)}:x=w-text_w-{width * 0.05}:y=h-text_h-{height * 0.05}"
            ),
        ]
        if silent_preview:
            filters.append(
                f"{drawtext_filter('SILENT REVIEW PREVIEW')}:fontcolor=0xf4c875:"
                f"fontsize={max(18, width // 55)}:x=(w-text_w)/2:y={height * 0.82}"
            )
        result = self.runner.run(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x08111f:s={width}x{height}:r={settings.frame_rate}:d={duration_seconds:.3f}",
                "-vf",
                ",".join(filters),
                "-c:v",
                settings.video_codec,
                "-preset",
                "ultrafast",
                "-pix_fmt",
                settings.pixel_format,
                "-an",
                str(target),
            ],
            output_path=target,
        )
        if not result.success:
            raise ValidationError(
                "FFmpeg failed to render a deterministic scene.",
                details={"command": result.command_summary, "error": result.error_message},
            )
        probe = self.runner.probe(target)
        warnings = [
            "Neutral local visualization placeholder; not generated live-action or anime footage."
        ]
        if silent_preview:
            warnings.append("SILENT REVIEW PREVIEW is visibly labelled.")
        artifact = completed_artifact(
            artifact_type=RenderArtifactType.SCENE_VIDEO,
            path=target,
            mime_type="video/mp4",
            sample_data=settings.sample_data,
            source_references=[f"storyboard-scene:{scene.scene_id}"],
            warnings=warnings,
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
        )
        return artifact, result.command_summary

    @staticmethod
    def _safe_text(value: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9 _-]+", "", value).strip()
        return (clean or "Production Scene")[:55]

    @staticmethod
    def _placeholder_label(style: VideoStyle) -> str:
        if style in {
            VideoStyle.ANIME,
            VideoStyle.LIVE_ACTION,
            VideoStyle.CINEMATIC_LIVE_ACTION,
        }:
            return f"{style.value.replace('_', ' ').upper()} CONCEPT PLACEHOLDER"
        return "DETERMINISTIC MOTION GRAPHICS"
