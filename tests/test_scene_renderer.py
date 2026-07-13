from pathlib import Path
import shutil

import pytest

from company_missions.local_render_pilot import create_review_ready_production_package
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import RenderSettings
from production.rendering.scene_renderer import DeterministicSceneRenderer


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg unavailable")
def test_scene_renderer_creates_real_review_mp4(tmp_path: Path) -> None:
    settings = RenderSettings(output_root=tmp_path, maximum_render_duration_seconds=5)
    runner = FFmpegRunner(ffmpeg_path=shutil.which("ffmpeg") or "ffmpeg", ffprobe_path=shutil.which("ffprobe") or "ffprobe", output_root=tmp_path)
    scene = create_review_ready_production_package().storyboard.scenes[0]
    artifact, _ = DeterministicSceneRenderer(runner).render(scene, tmp_path / "scene.mp4", settings, duration_seconds=1, scene_index=1, scene_count=1, silent_preview=True)
    assert artifact.path.is_file()
    assert artifact.width == settings.long_form_width
