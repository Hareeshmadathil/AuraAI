"""Strict loader for the approved Mission Zero revision package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core import ValidationError

from private_video_production.models import PrivateVideoProductionInput


class MissionZeroPackageLoader:
    """Load exact versioned artifacts without falling back to script-v1."""

    REQUIRED_FILES = (
        "mission/mission.json",
        "script/script-v1.json",
        "script/script-v2.json",
        "quality/revised/creative-quality.json",
        "revision/score-comparison.json",
        "founder-review/review-package.json",
        "production/revised/production-package.json",
        "manifest/sha256.json",
    )

    def load(self, package_root: Path, output_root: Path) -> PrivateVideoProductionInput:
        """Validate identity, lineage, quality, hashes, and safe state."""

        root = package_root.resolve()
        if not root.is_dir():
            raise ValidationError("Mission package directory does not exist.")
        values = {name: self._load_json(root, name) for name in self.REQUIRED_FILES}
        hashes = values["manifest/sha256.json"]
        self._validate_manifest_hash(root, "script/script-v2.json", hashes)

        mission = values["mission/mission.json"]
        script_v1 = values["script/script-v1.json"]
        script_v2 = values["script/script-v2.json"]
        quality = values["quality/revised/creative-quality.json"]
        comparison = values["revision/score-comparison.json"]
        review = values["founder-review/review-package.json"]
        production = values["production/revised/production-package.json"]

        mission_id = str(mission.get("mission_id", ""))
        if not mission_id or str(script_v2.get("mission_id")) != mission_id:
            raise ValidationError("Mission and script identities do not match.")
        if script_v2.get("version_number") != 2:
            raise ValidationError("Approved script-v2 is required; no fallback is allowed.")
        if script_v2.get("parent_artifact_id") != script_v1.get("artifact_id"):
            raise ValidationError("script-v2 must identify script-v1 as its parent.")
        if quality.get("gate", {}).get("status") != "passed":
            raise ValidationError("Revised Creative Quality gate has not passed.")
        blockers = int(comparison.get("revised_blocker_count", -1))
        score = float(comparison.get("revised_overall_score", -1))
        if score != 89.28 or blockers != 0:
            raise ValidationError("Mission Zero quality score or blocker count is invalid.")
        if mission.get("status") != "founder_review":
            raise ValidationError("Mission Zero must remain at founder review.")
        if review.get("rendered") is not False or review.get("published") is not False:
            raise ValidationError("Source package must be unrendered and unpublished.")
        if production.get("assembly_manifest", {}).get("render_status") != "not_rendered":
            raise ValidationError("Production package is not in the expected unrendered state.")

        return PrivateVideoProductionInput(
            mission_package=root,
            output_root=output_root.resolve(),
            mission_id=mission_id,
            script_artifact_id=script_v2["artifact_id"],
            script_version=script_v2["version_number"],
            script_parent_artifact_id=script_v2["parent_artifact_id"],
            script_content_hash=self._sha256(root / "script/script-v2.json"),
            quality_score=score,
            quality_gate="passed",
            blocker_count=blockers,
            founder_review_pending=True,
            rendered=False,
            published=False,
            title=script_v2["title"],
            hook=script_v2["hook"],
            sections=script_v2["sections"],
            estimated_duration_seconds=script_v2["estimated_duration_seconds"],
            source_subtitles=production.get("subtitle_package", {}).get("segments", []),
        )

    @staticmethod
    def _load_json(root: Path, relative_name: str) -> dict[str, Any]:
        target = (root / relative_name).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValidationError("Mission package path traversal was rejected.") from error
        if not target.is_file():
            raise ValidationError(f"Required mission artifact is missing: {relative_name}")
        try:
            value = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValidationError(f"Mission artifact is invalid: {relative_name}") from error
        if not isinstance(value, dict):
            raise ValidationError(f"Mission artifact must be an object: {relative_name}")
        return value

    def _validate_manifest_hash(
        self,
        root: Path,
        relative_name: str,
        manifest: dict[str, Any],
    ) -> None:
        expected = manifest.get(relative_name)
        actual = self._sha256(root / relative_name)
        if expected != actual:
            raise ValidationError(
                "Approved script content hash does not match the export manifest.",
                error_code="SCRIPT_CONTENT_HASH_MISMATCH",
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
