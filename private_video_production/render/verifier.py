"""FFprobe-backed verification beyond process exit status."""

from __future__ import annotations

import hashlib
from pathlib import Path

from private_video_production.models import (
    PrivateVideoStatus,
    RenderManifest,
    RenderResult,
)
from private_video_production.render.contracts import MediaCommandRunner


class PrivateRenderVerifier:
    """Verify file, streams, codecs, resolution, duration, and checksum."""

    def __init__(self, runner: MediaCommandRunner, output_root: Path) -> None:
        self._runner = runner
        self._root = output_root.resolve()

    def verify(self, manifest: RenderManifest) -> RenderResult:
        target = (self._root / manifest.specification.output_relative_path).resolve()
        warnings: list[str] = []
        if not target.is_file() or target.stat().st_size <= 0:
            return self._failed(manifest, "Private MP4 is missing or empty.")
        probe = self._runner.probe(target)
        spec = manifest.specification
        checks = [
            target.suffix.lower() == ".mp4",
            probe.has_video,
            probe.has_audio,
            probe.video_codec in {"h264", "avc1"},
            probe.audio_codec == "aac",
            probe.width == spec.width,
            probe.height == spec.height,
            abs(probe.duration_seconds - manifest.expected_duration_seconds) <= 8,
        ]
        if not all(checks):
            return self._failed(manifest, "FFprobe verification rejected the private draft.")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return RenderResult(
            manifest_id=manifest.manifest_id,
            status=PrivateVideoStatus.REVIEW_REQUIRED,
            output_relative_path=manifest.specification.output_relative_path,
            size_bytes=target.stat().st_size,
            duration_seconds=probe.duration_seconds,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
            width=probe.width,
            height=probe.height,
            frame_rate=float(spec.frame_rate),
            checksum_sha256=digest,
            verified=True,
            published=False,
            warnings=warnings,
        )

    @staticmethod
    def _failed(manifest: RenderManifest, warning: str) -> RenderResult:
        return RenderResult(
            manifest_id=manifest.manifest_id,
            status=PrivateVideoStatus.FAILED,
            verified=False,
            published=False,
            warnings=[warning],
        )
