"""Planning export, runtime events, dashboard, and regression boundaries."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_private_video_production_demo_app
from private_video_production.pipeline import PrivateVideoProductionPipeline
from private_video_production.voice import VoiceSynthesisService


PACKAGE = Path("outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a")


class NoVoiceAdapter:
    def list_voices(self):
        return []

    def synthesize_chunk(self, *, text, voice, output_path):
        raise AssertionError("Preparation must never synthesize narration.")


def test_prepare_exports_capture_timeline_and_no_media(tmp_path: Path) -> None:
    pipeline = PrivateVideoProductionPipeline(
        voice_service=VoiceSynthesisService(NoVoiceAdapter(), tmp_path),
    )
    result, output = pipeline.prepare(PACKAGE, tmp_path, export=True)

    assert output == tmp_path.resolve()
    assert (tmp_path / "founder-capture/capture-checklist.md").is_file()
    assert (tmp_path / "founder-capture/capture-manifest.json").is_file()
    assert (tmp_path / "timeline/timeline.json").is_file()
    assert (tmp_path / "timeline/ffmpeg-render-manifest.json").is_file()
    assert (tmp_path / "review/edit-notes-template.md").is_file()
    assert not list(tmp_path.rglob("*.wav"))
    assert not list(tmp_path.rglob("*.mp4"))
    assert result.production_input.quality_score == 89.28
    assert result.status.value == "blocked"
    assert "private_video_production_started" in result.runtime_events
    assert result.review.publishing_approved is False


def test_private_video_dashboard_is_safe_and_zero_argument() -> None:
    app = create_private_video_production_demo_app()
    response = TestClient(app).get("/private-video-production")

    assert response.status_code == 200
    assert "AuraAI Mission Zero" in response.text
    assert "Content Approval" in response.text
    assert "Private Render Approval" in response.text
    assert "NOT PUBLISHED" in response.text
    assert "Founder selection required" in response.text
    assert "I started AuraAI as a transcript-processing script" not in response.text


def test_dashboard_api_preserves_existing_fields_and_adds_projection() -> None:
    response = TestClient(create_private_video_production_demo_app()).get("/api/dashboard")
    body = response.json()

    assert response.status_code == 200
    assert "missions" in body
    assert "first_content_mission" in body
    assert body["private_video_production"]["published"] is False
    assert body["private_video_production"]["render_status"] == "not_rendered"
