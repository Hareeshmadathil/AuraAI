"""Deterministic placeholder scene rendering through injected FFmpeg."""

from __future__ import annotations

import re
from pathlib import Path

from core import ValidationError
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.graphics import drawtext_filter

from private_video_production.models import RenderSpecification, ScenePlan


class PrivateSceneRenderer:
    """Render branded motion cards; never impersonate missing evidence."""

    def __init__(self, runner: FFmpegRunner, output_root: Path) -> None:
        self._runner = runner
        self._root = output_root.resolve()

    def render(
        self,
        scene: ScenePlan,
        specification: RenderSpecification,
        relative_path: Path,
        *,
        source_asset: Path | None = None,
    ) -> Path:
        target = (self._root / relative_path).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as error:
            raise ValidationError("Scene output escapes the configured root.") from error
        target.parent.mkdir(parents=True, exist_ok=True)
        duration = scene.expected_end_seconds - scene.expected_start_seconds
        heading = re.sub(r"[^a-zA-Z0-9 _-]+", "", scene.visual.on_screen_text)[:70]
        label = scene.visual.placeholder_watermark or "AURAAI PRIVATE PRODUCTION"
        filters = [
            "drawbox=x=0:y=0:w=iw:h=ih:color=0x07111f:t=fill",
            "drawbox=x=0:y=0:w=iw:h=10:color=0x62e6c5:t=fill",
            "drawbox=x='mod(t*75\\,w+500)-500':y=h*0.20:w=500:h=4:color=0x62e6c5@0.55:t=fill",
            "drawbox=x='w-mod(t*48\\,w+360)':y=h*0.82:w=360:h=3:color=0x79a8ff@0.45:t=fill",
            f"{drawtext_filter(heading)}:fontcolor=white:fontsize=54:x=(w-text_w)/2:y=(h-text_h)/2",
            f"{drawtext_filter(label)}:fontcolor=0xf4c875:fontsize=25:x=(w-text_w)/2:y=h*0.75",
            f"{drawtext_filter('INTERNAL REVIEW - NOT FOR PUBLICATION')}:fontcolor=white@0.75:fontsize=22:x=40:y=h-55",
        ]
        if source_asset is None:
            arguments = [
                "-y", "-f", "lavfi", "-i",
                f"color=c=0x07111f:s={specification.width}x{specification.height}:r={specification.frame_rate}:d={duration:.3f}",
                "-vf", ",".join(filters), "-c:v", specification.video_codec,
                "-preset", specification.preset, "-pix_fmt", specification.pixel_format,
                "-an", str(target),
            ]
        else:
            asset = source_asset.resolve()
            try:
                asset.relative_to(self._root)
            except ValueError as error:
                raise ValidationError("Founder scene asset escapes the configured root.") from error
            if not asset.is_file():
                raise ValidationError("Founder scene asset is missing.")
            source_arguments = (
                ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(asset)]
                if asset.suffix.lower() in {".png", ".jpg", ".jpeg"}
                else ["-stream_loop", "-1", "-i", str(asset), "-t", f"{duration:.3f}"]
            )
            evidence_filters = [
                f"scale={specification.width}:{specification.height}:force_original_aspect_ratio=decrease",
                f"pad={specification.width}:{specification.height}:(ow-iw)/2:(oh-ih)/2:0x07111f",
                f"{drawtext_filter('VERIFIED FOUNDER-SUPPLIED EVIDENCE')}:fontcolor=0x62e6c5:fontsize=20:x=35:y=35",
                f"{drawtext_filter('INTERNAL REVIEW - NOT FOR PUBLICATION')}:fontcolor=white@0.75:fontsize=22:x=40:y=h-55",
            ]
            arguments = [
                "-y", *source_arguments, "-vf", ",".join(evidence_filters),
                "-r", str(specification.frame_rate), "-c:v", specification.video_codec,
                "-preset", specification.preset, "-pix_fmt", specification.pixel_format,
                "-an", str(target),
            ]
        result = self._runner.run(
            arguments,
            output_path=target,
            timeout_seconds=max(60, duration * 4),
        )
        if not result.success:
            raise ValidationError("Private placeholder scene rendering failed.")
        return target
