from pathlib import Path

import pytest

from company_missions.local_render_pilot import create_review_ready_production_package
from core import ValidationError
from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import RenderSettings
from production.rendering.video_renderer import LocalVideoRenderer


def test_video_renderer_requires_explicit_founder_approval(tmp_path: Path) -> None:
    package = create_review_ready_production_package()
    runner = FFmpegRunner(ffmpeg_path="ffmpeg", ffprobe_path="ffprobe", output_root=tmp_path)
    with pytest.raises(ValidationError):
        LocalVideoRenderer(runner).render(package=package, scene_paths=[], voice_path=tmp_path / "voice.wav", subtitle_path=tmp_path / "captions.srt", output_path=tmp_path / "video.mp4", settings=RenderSettings(output_root=tmp_path), founder_render_approved=False, silent_fallback=False)
