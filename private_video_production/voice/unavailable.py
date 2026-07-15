"""Explicit unavailable voice adapter; never creates fake narration."""

from pathlib import Path

from core import DependencyUnavailableError

from private_video_production.models import VoiceProfile


class UnavailableVoiceAdapter:
    """Network-free adapter used when no local TTS is available."""

    def list_voices(self) -> list[VoiceProfile]:
        return []

    def synthesize_chunk(
        self,
        *,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
    ) -> None:
        raise DependencyUnavailableError(
            "No local synthetic voice is available; narration was not created.",
            dependency_name="windows_sapi",
        )
