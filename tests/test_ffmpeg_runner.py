from pathlib import Path

import pytest

from core import ValidationError
from production.rendering.ffmpeg_runner import FFmpegRunner


def test_runner_rejects_output_traversal(tmp_path: Path) -> None:
    runner = FFmpegRunner(
        ffmpeg_path="ffmpeg", ffprobe_path="ffprobe", output_root=tmp_path
    )
    with pytest.raises(ValidationError):
        runner.require_output_path(tmp_path.parent / "outside.mp4")


def test_runner_rejects_command_strings(tmp_path: Path) -> None:
    runner = FFmpegRunner(
        ffmpeg_path="ffmpeg", ffprobe_path="ffprobe", output_root=tmp_path
    )
    with pytest.raises(ValidationError):
        runner.run("-version")
