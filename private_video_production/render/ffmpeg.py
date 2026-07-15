"""Safe argument-list construction for a private H.264/AAC draft."""

from __future__ import annotations

from pathlib import Path

from production.rendering.graphics import drawtext_filter

from private_video_production.models import RenderSpecification


class PrivateFFmpegCommandBuilder:
    """Construct a bounded FFmpeg command without shell execution."""

    def build(
        self,
        *,
        concat_file: Path,
        narration_file: Path,
        subtitle_file: Path | None,
        output_file: Path,
        specification: RenderSpecification,
    ) -> list[str]:
        filters = [
            f"{drawtext_filter(specification.watermark.replace('—', '-'))}:"
            "fontcolor=white@0.72:fontsize=24:x=35:y=h-th-35"
        ]
        if subtitle_file is not None:
            escaped = str(subtitle_file.resolve()).replace("\\", "/").replace(":", "\\:")
            filters.insert(0, f"subtitles='{escaped}':force_style='MarginV=55,Fontsize=20'")
        return [
            "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(narration_file),
            "-vf", ",".join(filters),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", specification.video_codec,
            "-preset", specification.preset,
            "-crf", str(specification.crf),
            "-pix_fmt", specification.pixel_format,
            "-r", str(specification.frame_rate),
            "-c:a", specification.audio_codec,
            "-b:a", "160k",
            "-movflags", "+faststart",
            "-shortest",
            str(output_file),
        ]
