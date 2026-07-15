"""Provider-neutral contracts for offline voice synthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from private_video_production.models import VoiceProfile


class LocalVoiceAdapter(Protocol):
    """Replaceable network-free voice adapter."""

    def list_voices(self) -> list[VoiceProfile]: ...

    def synthesize_chunk(
        self,
        *,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
    ) -> None: ...
