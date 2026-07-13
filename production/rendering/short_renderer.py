"""Local vertical short-form review pilot rendering."""

from __future__ import annotations

import re
from pathlib import Path

from core import ValidationError
from production.models import ShortFormAsset
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.graphics import drawtext_filter
from production.rendering.models import RenderArtifactType, RenderSettings, RenderedArtifact
from production.rendering.validation import completed_artifact


class LocalShortRenderer:
    """Render one platform-neutral vertical short with safe text margins."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner

    def render(
        self,
        *,
        asset: ShortFormAsset,
        output_path: Path,
        settings: RenderSettings,
        voice_path: Path | None,
        silent_fallback: bool,
        duration_seconds: float = 20.0,
    ) -> tuple[RenderedArtifact, list[str]]:
        """Create one real 9:16 MP4 without publishing it."""

        duration = min(45.0, max(15.0, duration_seconds))
        target = self.runner.require_output_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        hook = self._safe_text(asset.hook, 55)
        cta = self._safe_text(asset.call_to_action, 45)
        width, height = settings.short_width, settings.short_height
        filters = [
            "drawbox=x=0:y=0:w=iw:h=ih:color=0x08111f:t=fill",
            "drawbox=x=45:y=90:w=630:h=1100:color=0x101f35:t=fill",
            f"{drawtext_filter('LOCAL SHORT REVIEW')}:fontcolor=0x62e6c5:fontsize=26:x=(w-text_w)/2:y=150",
            f"{drawtext_filter(hook)}:fontcolor=white:fontsize=42:x=(w-text_w)/2:y=430",
            f"{drawtext_filter(cta)}:fontcolor=0x79a8ff:fontsize=28:x=(w-text_w)/2:y=920",
            f"{drawtext_filter('REVIEW REQUIRED - NOT PUBLISHED')}:fontcolor=0xf4c875:fontsize=21:x=(w-text_w)/2:y=1110",
        ]
        if silent_fallback:
            filters.append(
                f"{drawtext_filter('SILENT REVIEW PREVIEW')}:fontcolor=0xf4c875:fontsize=23:x=(w-text_w)/2:y=1040"
            )
        arguments = [
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x08111f:s={width}x{height}:r={settings.frame_rate}:d={duration:.3f}",
        ]
        if voice_path is not None:
            arguments.extend(["-i", str(voice_path.resolve())])
        arguments.extend(
            [
                "-vf",
                ",".join(filters),
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
        result = self.runner.run(arguments, output_path=target)
        if not result.success:
            raise ValidationError("FFmpeg failed to render the vertical short pilot.")
        probe = self.runner.probe(target)
        warnings = [
            "One platform-neutral derivative rendered; remaining concepts stay planned."
        ]
        if silent_fallback:
            warnings.append("SILENT REVIEW PREVIEW: audio contains no narration.")
        artifact = completed_artifact(
            artifact_type=RenderArtifactType.SHORT_FORM_VIDEO,
            path=target,
            mime_type="video/mp4",
            sample_data=settings.sample_data,
            source_references=[f"short-form-asset:{asset.asset_id}"],
            warnings=warnings,
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
        )
        return artifact, result.command_summary

    @staticmethod
    def _safe_text(value: str, limit: int) -> str:
        clean = re.sub(r"[^a-zA-Z0-9 _-]+", "", value).strip()
        return (clean or "Review this concept")[:limit]
