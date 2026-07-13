"""High-contrast local PNG thumbnail rendering through FFmpeg."""

from __future__ import annotations

import re
from pathlib import Path

from core import ValidationError
from production.models import ThumbnailPlan
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.graphics import drawtext_filter
from production.rendering.models import RenderArtifactType, RenderSettings, RenderedArtifact
from production.rendering.validation import completed_artifact


class LocalThumbnailRenderer:
    """Render the recommended concept without fonts, APIs, or copyrighted media."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner

    def render(
        self,
        plan: ThumbnailPlan,
        output_path: Path,
        settings: RenderSettings,
    ) -> tuple[RenderedArtifact, list[str]]:
        """Create one real 1280x720 PNG from the recommended concept."""

        concept = next(
            item for item in plan.concepts if item.concept_id == plan.recommended_concept_id
        )
        target = self.runner.require_output_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = self._safe_text(concept.primary_text)
        filters = ",".join(
            [
                "drawbox=x=0:y=0:w=iw:h=ih:color=0x08111f:t=fill",
                "drawbox=x=70:y=70:w=1140:h=580:color=0x101f35:t=fill",
                "drawbox=x=70:y=70:w=18:h=580:color=0x62e6c5:t=fill",
                f"{drawtext_filter('LOCAL REVIEW THUMBNAIL')}:fontcolor=0x79a8ff:fontsize=28:x=130:y=135",
                f"{drawtext_filter(text)}:fontcolor=white:fontsize=88:x=(w-text_w)/2:y=(h-text_h)/2",
                f"{drawtext_filter('DETERMINISTIC - NOT PUBLISHED')}:fontcolor=0xf4c875:fontsize=25:x=(w-text_w)/2:y=570",
            ]
        )
        result = self.runner.run(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x08111f:s=1280x720:d=1",
                "-vf",
                filters,
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-update",
                "1",
                str(target),
            ],
            output_path=target,
        )
        if not result.success:
            raise ValidationError("FFmpeg failed to render the local thumbnail.")
        probe = self.runner.probe(target)
        artifact = completed_artifact(
            artifact_type=RenderArtifactType.THUMBNAIL,
            path=target,
            mime_type="image/png",
            sample_data=settings.sample_data,
            source_references=[f"thumbnail-concept:{concept.concept_id}"],
            warnings=["Local deterministic graphic; review required and not published."],
            width=probe.width,
            height=probe.height,
        )
        return artifact, result.command_summary

    @staticmethod
    def _safe_text(value: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9 _-]+", "", value).strip()
        return (clean or "REVIEW THIS")[:35]
