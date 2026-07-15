"""Explicit local composition of voice and FFmpeg dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from production.rendering.capabilities import RenderCapabilityDetector
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import RenderCapability

from private_video_production.voice import (
    UnavailableVoiceAdapter,
    VoiceSynthesisService,
    WindowsSapiAdapter,
)


@dataclass(frozen=True)
class PrivateVideoComposition:
    """Local, network-free production dependencies."""

    capabilities: tuple[RenderCapability, ...]
    voice_service: VoiceSynthesisService
    ffmpeg_runner: FFmpegRunner | None

    @classmethod
    def create(cls, output_root: Path) -> "PrivateVideoComposition":
        detector = RenderCapabilityDetector()
        capabilities = tuple(detector.detect())
        paths = detector.locate_executables()
        sapi = next(item for item in capabilities if item.capability_name == "windows_sapi")
        adapter = (
            WindowsSapiAdapter(powershell_path=paths.get("powershell") or "powershell")
            if sapi.available
            else UnavailableVoiceAdapter()
        )
        ffmpeg = next(item for item in capabilities if item.capability_name == "ffmpeg")
        ffprobe = next(item for item in capabilities if item.capability_name == "ffprobe")
        runner = None
        if ffmpeg.available and ffprobe.available:
            runner = FFmpegRunner(
                ffmpeg_path=paths["ffmpeg"] or "ffmpeg",
                ffprobe_path=paths["ffprobe"] or "ffprobe",
                output_root=output_root,
                timeout_seconds=900,
            )
        return cls(
            capabilities=capabilities,
            voice_service=VoiceSynthesisService(adapter, output_root),
            ffmpeg_runner=runner,
        )
