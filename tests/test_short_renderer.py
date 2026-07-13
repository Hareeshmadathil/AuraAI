from pathlib import Path
import shutil

import pytest

from company_missions.local_render_pilot import create_review_ready_production_package
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import RenderSettings
from production.rendering.short_renderer import LocalShortRenderer


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg unavailable")
def test_short_renderer_creates_vertical_mp4(tmp_path: Path) -> None:
    package = create_review_ready_production_package()
    settings = RenderSettings(output_root=tmp_path, maximum_render_duration_seconds=15)
    runner = FFmpegRunner(ffmpeg_path=shutil.which("ffmpeg") or "ffmpeg", ffprobe_path=shutil.which("ffprobe") or "ffprobe", output_root=tmp_path)
    artifact, _ = LocalShortRenderer(runner).render(asset=package.short_form_package.assets[0], output_path=tmp_path / "short.mp4", settings=settings, voice_path=None, silent_fallback=True, duration_seconds=15)
    assert artifact.height > artifact.width
    assert artifact.published is False
