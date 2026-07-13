from pathlib import Path

from company_missions.local_render_pilot import create_review_ready_production_package
from production.rendering.models import RenderCapability, RenderEngine
from production.rendering.voice_renderer import OfflineVoiceRenderer


def test_explicit_silent_voice_fallback_is_labelled(tmp_path: Path) -> None:
    package = create_review_ready_production_package()
    outcome = OfflineVoiceRenderer(output_root=tmp_path).render(
        package.voiceover_plan,
        tmp_path / "voice.wav",
        RenderCapability(
            capability_name="windows_sapi", available=False, message="not available"
        ),
        allow_silent_fallback=True,
        maximum_duration_seconds=5,
    )
    assert outcome.engine == RenderEngine.SILENT_FALLBACK
    assert outcome.artifact is not None
    assert outcome.artifact.duration_seconds == 5
    assert "SILENT REVIEW PREVIEW" in outcome.artifact.warnings[0]
