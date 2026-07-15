"""Safe explicit export of plans, capture guidance, timelines, and review state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core import ValidationError
from pydantic import TypeAdapter

from private_video_production.assets.placeholders import PlaceholderFactory
from private_video_production.models import PrivateVideoProductionResult
from private_video_production.review.exporter import EDIT_NOTES_TEMPLATE, review_markdown
from private_video_production.subtitles import serialize_srt


class PrivateVideoProductionExporter:
    """Write only beneath an injected output root when explicitly called."""

    def __init__(self, output_root: Path) -> None:
        self._root = output_root.resolve()

    def export(self, result: PrivateVideoProductionResult) -> Path:
        """Export production metadata without copying the approved script."""

        target = self._root
        self._require_safe(target)
        target.mkdir(parents=True, exist_ok=True)
        files: list[Path] = []
        files.append(self._json(target, "production/input-summary.json", {
            "mission_id": str(result.production_input.mission_id),
            "script_artifact_id": str(result.production_input.script_artifact_id),
            "script_version": result.production_input.script_version,
            "script_content_hash": result.production_input.script_content_hash,
            "quality_score": result.production_input.quality_score,
            "quality_gate": result.production_input.quality_gate,
            "blocker_count": result.production_input.blocker_count,
            "rendered": False,
            "published": False,
        }))
        files.append(self._json(target, "scenes/scene-plan.json", result.scenes))
        files.append(self._json(target, "assets/asset-requirements.json", result.asset_requirements))
        files.append(self._json(target, "assets/asset-validation.json", result.asset_validation))
        files.extend(self._capture_pack(target, result))
        placeholder_factory = PlaceholderFactory(target)
        for requirement in result.asset_requirements:
            files.append(placeholder_factory.create(requirement))
        files.append(self._write(target, "subtitles/mission-zero.srt", serialize_srt(result.subtitles)))
        files.append(self._json(target, "subtitles/subtitle-track.json", result.subtitles))
        files.append(self._json(target, "timeline/timeline.json", result.timeline_tracks))
        files.append(self._json(target, "timeline/edit-decision-list.json", {
            "tracks": result.timeline_tracks,
            "transitions": result.transitions,
            "markers": result.markers,
        }))
        files.append(self._write(target, "timeline/timeline.md", self._timeline_md(result)))
        files.append(self._json(target, "timeline/ffmpeg-render-manifest.json", result.render_manifest))
        files.append(self._json(target, "audio/audio-mix-plan.json", result.audio_mix))
        if result.approval:
            files.append(self._json(target, "approvals/private-video-approval.json", result.approval))
        files.append(self._json(target, "runtime/events.json", result.runtime_events))
        if result.render_result:
            files.append(self._json(target, "render/render-verification.json", result.render_result))
            files.append(self._write(target, "render/render-verification.md", self._verification_md(result)))
        if result.review:
            files.append(self._json(target, "review/private-video-review.json", result.review))
            files.append(self._write(target, "review/private-video-review.md", review_markdown(result.review)))
        else:
            files.append(self._write(target, "review/private-video-review.md", "# Private video review\n\nPending. NOT PUBLISHED.\n"))
        files.append(self._write(target, "review/edit-notes-template.md", EDIT_NOTES_TEMPLATE))
        checksum_values = {
            str(path.relative_to(target)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files if path.is_file()
        }
        self._json(target, "manifest/sha256.json", checksum_values)
        return target

    def _capture_pack(
        self,
        target: Path,
        result: PrivateVideoProductionResult,
    ) -> list[Path]:
        lines = ["# Mission Zero founder capture checklist", ""]
        manifest: list[dict[str, Any]] = []
        for requirement in result.asset_requirements:
            lines.extend([
                f"## {requirement.asset_id}: {requirement.description}", "",
                f"- Scenes: {', '.join(requirement.scene_ids)}",
                f"- Action: {requirement.capture_instructions}",
                f"- Target: {requirement.target_relative_path}",
                f"- Capture: {requirement.recommended_width}×{requirement.recommended_height} at {requirement.frame_rate or 30} fps",
                "- Hide: API keys, .env, email, recovery codes, notifications, private data, and unrelated files.",
                "- Cursor: move only when it explains the action.", "",
            ])
            manifest.append(requirement.model_dump(mode="json"))
        return [
            self._write(target, "founder-capture/capture-checklist.md", "\n".join(lines)),
            self._json(target, "founder-capture/capture-manifest.json", manifest),
            self._write(target, "founder-capture/recording-settings.md", (
                "# Recording settings\n\n1920×1080, 30 fps, clean desktop, notifications disabled. "
                "Hide bookmarks, private tabs, API keys, .env, email, recovery codes, and personal files.\n"
            )),
            self._write(target, "founder-capture/folder-guide.md", (
                "# Folder guide\n\nPlace captures under `founder-assets/` using the filenames in the manifest. "
                "Do not place secrets or unrelated personal data in this directory.\n"
            )),
        ]

    def _json(self, root: Path, relative: str, value: Any) -> Path:
        value = TypeAdapter(Any).dump_python(value, mode="json")
        return self._write(root, relative, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))

    def _write(self, root: Path, relative: str, text: str) -> Path:
        target = (root / relative).resolve()
        self._require_safe(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def _require_safe(self, path: Path) -> None:
        try:
            path.relative_to(self._root)
        except ValueError as error:
            raise ValidationError("Private video export escapes its safe root.") from error

    @staticmethod
    def _timeline_md(result: PrivateVideoProductionResult) -> str:
        duration = result.render_manifest.expected_duration_seconds if result.render_manifest else 0
        return (
            "# Mission Zero private video timeline\n\n"
            f"Duration: {duration:.2f} seconds\n\n"
            f"Scenes: {len(result.scenes)}\n\n"
            f"Placeholders: {sum(scene.founder_capture_required for scene in result.scenes)}\n\n"
            "Publishing: NOT APPROVED\n"
        )

    @staticmethod
    def _verification_md(result: PrivateVideoProductionResult) -> str:
        verification = result.render_result
        return (
            "# Private render verification\n\n"
            f"Verified: {bool(verification and verification.verified)}\n\n"
            "Published: false\n"
        )
