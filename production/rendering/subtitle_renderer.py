"""Explicit UTF-8 subtitle sidecar export."""

from __future__ import annotations

from pathlib import Path

from core import ValidationError
from production.models import SubtitlePackage
from production.rendering.models import RenderArtifactType, RenderSettings, RenderedArtifact
from production.rendering.validation import completed_artifact


class SubtitleFileExporter:
    """Save validated SRT and WebVTT content only when called."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()

    def export(
        self,
        package: SubtitlePackage,
        directory: Path,
        settings: RenderSettings,
    ) -> list[RenderedArtifact]:
        """Write both subtitle formats with traversal protection."""

        self._validate_timing(package)
        safe_directory = self._safe_path(directory)
        safe_directory.mkdir(parents=True, exist_ok=True)
        srt_path = safe_directory / "captions.srt"
        vtt_path = safe_directory / "captions.vtt"
        self._write(srt_path, package.srt_text, settings.overwrite)
        self._write(vtt_path, package.vtt_text, settings.overwrite)
        return [
            completed_artifact(
                artifact_type=RenderArtifactType.SUBTITLE_SRT,
                path=srt_path,
                mime_type="application/x-subrip",
                sample_data=settings.sample_data,
                source_references=[f"subtitle-package:{package.package_id}"],
            ),
            completed_artifact(
                artifact_type=RenderArtifactType.SUBTITLE_VTT,
                path=vtt_path,
                mime_type="text/vtt",
                sample_data=settings.sample_data,
                source_references=[f"subtitle-package:{package.package_id}"],
            ),
        ]

    @staticmethod
    def _validate_timing(package: SubtitlePackage) -> None:
        for expected, segment in enumerate(package.segments, start=1):
            if segment.index != expected:
                raise ValidationError("Subtitle indexes must remain sequential.")
            if segment.end_seconds <= segment.start_seconds:
                raise ValidationError("Subtitle segment duration is invalid.")
            if expected > 1 and segment.start_seconds < package.segments[expected - 2].end_seconds:
                raise ValidationError("Subtitle timings cannot overlap.")

    @staticmethod
    def _write(path: Path, content: str, overwrite: bool) -> None:
        if path.exists() and not overwrite:
            raise ValidationError(f"Subtitle output already exists: {path.name}.")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(path)

    def _safe_path(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.output_root)
        except ValueError as error:
            raise ValidationError("Subtitle path escapes the configured output root.") from error
        return resolved
