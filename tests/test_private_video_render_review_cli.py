"""FFmpeg boundary, private review, export, and CLI safety tests."""

from pathlib import Path
from uuid import uuid4

import pytest

from core import ValidationError
from private_video_production.approvals import PrivateVideoApprovalService
from private_video_production.cli import main
from private_video_production.loader import MissionZeroPackageLoader
from private_video_production.models import (
    AssetValidationResult,
    PrivateVideoReview,
    RenderManifest,
    RenderSpecification,
    ReviewDecision,
    VoiceSynthesisResult,
)
from private_video_production.render.service import PrivateRenderService
from private_video_production.review import PrivateVideoReviewService
from production.rendering.models import FFmpegCommandResult, MediaProbe


PACKAGE = Path("outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a")


class FakeRunner:
    def __init__(self, *, success=True, timed_out=False):
        self.success = success
        self.timed_out = timed_out
        self.arguments = None

    def run(self, arguments, *, output_path=None, timeout_seconds=None):
        self.arguments = list(arguments)
        if self.success and output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"private-mp4")
        return FFmpegCommandResult(
            success=self.success,
            return_code=0 if self.success else -1,
            command_summary=["ffmpeg", "[safe arguments]"],
            timed_out=self.timed_out,
            error_message="Local render timed out." if self.timed_out else None,
        )

    def probe(self, path):
        return MediaProbe(
            path=path,
            duration_seconds=5,
            width=1280,
            height=720,
            video_codec="h264",
            audio_codec="aac",
            has_video=True,
            has_audio=True,
        )


def _render_values(tmp_path: Path):
    production_input = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    approval = PrivateVideoApprovalService().record(
        production_input,
        content_approved=True,
        private_render_approved=True,
        founder_confirmed=True,
    )
    scene = tmp_path / "scenes/scene-001.mp4"
    scene.parent.mkdir(parents=True)
    scene.write_bytes(b"scene")
    narration = tmp_path / "voice/narration.wav"
    narration.parent.mkdir(parents=True)
    narration.write_bytes(b"wav")
    voice = VoiceSynthesisResult(
        request_id=uuid4(),
        success=True,
        available=True,
        voice_name="Local Voice",
        output_relative_path="voice/narration.wav",
        duration_seconds=5,
        sample_rate=48000,
        channels=1,
        chunks_created=1,
        message="Local narration ready.",
    )
    specification = RenderSpecification(
        width=1280,
        height=720,
        preview=True,
        output_relative_path="render/AuraAI_Mission_Zero_PRIVATE_PREVIEW_v1.mp4",
    )
    manifest = RenderManifest(
        mission_id=production_input.mission_id,
        specification=specification,
        scene_relative_paths=[Path("scenes/scene-001.mp4")],
        narration_relative_path=Path("voice/narration.wav"),
        expected_duration_seconds=5,
        placeholder_count=1,
    )
    return production_input, approval, voice, manifest


def test_mocked_private_render_uses_safe_arguments_and_verifies(tmp_path: Path) -> None:
    production_input, approval, voice, manifest = _render_values(tmp_path)
    runner = FakeRunner()
    result = PrivateRenderService(runner, tmp_path).render(
        production_input=production_input,
        approval=approval,
        manifest=manifest,
        voice_result=voice,
        asset_validation=AssetValidationResult(valid=True),
        allow_placeholder_preview=True,
    )

    assert result.verified is True
    assert result.published is False
    assert "libx264" in runner.arguments
    assert "+faststart" in runner.arguments
    assert all(argument != "shell=True" for argument in runner.arguments)


def test_render_requires_approval_and_reports_timeout(tmp_path: Path) -> None:
    production_input, approval, voice, manifest = _render_values(tmp_path)
    with pytest.raises(ValidationError) as caught:
        PrivateRenderService(FakeRunner(), tmp_path).render(
            production_input=production_input,
            approval=None,
            manifest=manifest,
            voice_result=voice,
            asset_validation=AssetValidationResult(valid=True),
            allow_placeholder_preview=True,
        )
    assert caught.value.error_code == "CONTENT_APPROVAL_REQUIRED"
    failed = PrivateRenderService(FakeRunner(success=False, timed_out=True), tmp_path).render(
        production_input=production_input,
        approval=approval,
        manifest=manifest,
        voice_result=voice,
        asset_validation=AssetValidationResult(valid=True),
        allow_placeholder_preview=True,
    )
    assert failed.verified is False
    assert "timed out" in failed.warnings[0]


def test_private_review_options_never_approve_publishing(tmp_path: Path) -> None:
    _, _, _, manifest = _render_values(tmp_path)
    runner = FakeRunner()
    output = tmp_path / manifest.specification.output_relative_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"private-mp4")
    render = PrivateRenderService(runner, tmp_path)._verifier.verify(manifest)
    review = PrivateVideoReview(
        mission_id=manifest.mission_id,
        render_manifest_id=manifest.manifest_id,
        placeholder_count=1,
    )
    revised = PrivateVideoReviewService().decide(
        review,
        render,
        ReviewDecision.REQUEST_EDIT,
        founder_confirmed=True,
        notes="Replace evidence placeholders.",
    )
    assert revised.decision == ReviewDecision.REQUEST_EDIT
    assert revised.publishing_approved is False


def test_cli_rejects_production_without_mission_package(capsys) -> None:
    assert main(["--prepare"]) == 2
    assert "mission-package" in capsys.readouterr().err
