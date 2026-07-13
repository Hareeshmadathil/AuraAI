from pathlib import Path
import shutil

import pytest

from company_missions.local_render_pilot import create_review_ready_production_package
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import RenderSettings
from production.rendering.thumbnail_renderer import LocalThumbnailRenderer


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg unavailable")
def test_thumbnail_renderer_creates_1280_by_720_png(tmp_path: Path) -> None:
    settings = RenderSettings(output_root=tmp_path)
    runner = FFmpegRunner(ffmpeg_path=shutil.which("ffmpeg") or "ffmpeg", ffprobe_path=shutil.which("ffprobe") or "ffprobe", output_root=tmp_path)
    artifact, _ = LocalThumbnailRenderer(runner).render(create_review_ready_production_package().thumbnail_plan, tmp_path / "thumbnail.png", settings)
    assert (artifact.width, artifact.height) == (1280, 720)
