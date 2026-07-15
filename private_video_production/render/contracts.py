"""Injected private-render execution contract."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from production.rendering.models import FFmpegCommandResult, MediaProbe


class MediaCommandRunner(Protocol):
    """Safe FFmpeg/FFprobe boundary used by the private renderer."""

    def run(
        self,
        arguments: Sequence[str],
        *,
        output_path: Path | None = None,
        timeout_seconds: float | None = None,
    ) -> FFmpegCommandResult: ...

    def probe(self, path: Path) -> MediaProbe: ...
