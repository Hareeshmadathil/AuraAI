"""Founder-gated private MP4 assembly using injected FFmpeg."""

from __future__ import annotations

from pathlib import Path

from core import ValidationError

from private_video_production.approvals import PrivateVideoApprovalService
from private_video_production.models import (
    AssetValidationResult,
    PrivateVideoApproval,
    PrivateVideoProductionInput,
    PrivateVideoStatus,
    RenderManifest,
    RenderResult,
    VoiceSynthesisResult,
)
from private_video_production.render.contracts import MediaCommandRunner
from private_video_production.render.ffmpeg import PrivateFFmpegCommandBuilder
from private_video_production.render.verifier import PrivateRenderVerifier


class PrivateRenderService:
    """Assemble a local review MP4 only after both founder gates."""

    def __init__(self, runner: MediaCommandRunner, output_root: Path) -> None:
        self._runner = runner
        self._root = output_root.resolve()
        self._commands = PrivateFFmpegCommandBuilder()
        self._verifier = PrivateRenderVerifier(runner, output_root)

    def render(
        self,
        *,
        production_input: PrivateVideoProductionInput,
        approval: PrivateVideoApproval | None,
        manifest: RenderManifest,
        voice_result: VoiceSynthesisResult | None,
        asset_validation: AssetValidationResult,
        allow_placeholder_preview: bool,
    ) -> RenderResult:
        PrivateVideoApprovalService.require_private_render(approval, production_input)
        if voice_result is None or not voice_result.success or not voice_result.output_relative_path:
            raise ValidationError("Real local narration is required before video rendering.")
        if asset_validation.missing_asset_ids and not allow_placeholder_preview:
            raise ValidationError("Required founder assets are missing.")
        scene_paths = [(self._root / path).resolve() for path in manifest.scene_relative_paths]
        if not scene_paths or any(not path.is_file() for path in scene_paths):
            raise ValidationError("Rendered scene clips are required before assembly.")
        output = (self._root / manifest.specification.output_relative_path).resolve()
        narration = (self._root / voice_result.output_relative_path).resolve()
        subtitle = (
            (self._root / manifest.subtitle_relative_path).resolve()
            if manifest.subtitle_relative_path
            else None
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        concat = output.parent / ".private-scenes.concat.txt"
        concat.write_text(
            "\n".join(f"file '{str(path).replace('\\', '/').replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for path in scene_paths) + "\n",
            encoding="utf-8",
        )
        arguments = self._commands.build(
            concat_file=concat,
            narration_file=narration,
            subtitle_file=subtitle if subtitle and subtitle.is_file() else None,
            output_file=output,
            specification=manifest.specification,
        )
        try:
            command_result = self._runner.run(
                arguments,
                output_path=output,
                timeout_seconds=max(600, manifest.expected_duration_seconds * 5),
            )
        finally:
            concat.unlink(missing_ok=True)
        if not command_result.success:
            return RenderResult(
                manifest_id=manifest.manifest_id,
                status=PrivateVideoStatus.FAILED,
                verified=False,
                published=False,
                warnings=[command_result.error_message or "FFmpeg render failed."],
            )
        return self._verifier.verify(manifest)
