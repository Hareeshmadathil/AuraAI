"""Strict, path-safe loader for the approved Mission Zero revision."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core import ValidationError
from production_connector.models import MissionPackage

MISSION_ID = "f7385664-ac50-4e16-83c1-339781135a0a"


class MissionPackageLoader:
    """Load script v2 and validate its mission and quality lineage."""

    def __init__(self, allowed_root: Path | None = None) -> None:
        self._allowed_root = (allowed_root or Path.cwd()).resolve()

    def load(self, path: Path) -> MissionPackage:
        root = path.resolve()
        try:
            root.relative_to(self._allowed_root)
        except ValueError as error:
            raise ValidationError("Mission package path is unsafe.", error_code="UNSAFE_MISSION_PACKAGE_PATH") from error
        script_path = root / "script" / "script-v2.json"
        if not script_path.is_file():
            raise ValidationError("script-v2 is required; script-v1 fallback is forbidden.", error_code="SCRIPT_V2_REQUIRED")
        try:
            script = self._json(script_path)
            mission = self._json(root / "mission" / "mission.json")
            history = self._json(root / "mission" / "artifact-version-history.json")
            quality = self._json(root / "quality" / "revised" / "creative-quality.json")
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValidationError("Mission package validation failed.", error_code="INVALID_MISSION_PACKAGE") from error
        scripts = [item for item in history if item.get("artifact_type") == "script"]
        v1 = next((item for item in scripts if item.get("version_number") == 1), None)
        v2 = next((item for item in scripts if item.get("version_number") == 2), None)
        gate = quality["gate"]
        valid = (
            str(script["mission_id"]) == MISSION_ID == str(mission["mission_id"])
            and script["version_number"] == 2 and v1 and v2
            and script["parent_artifact_id"] == v1["metadata"]["typed_artifact_id"]
            and v2["parent_artifact_id"] == v1["artifact_id"]
            and float(gate["actual_score"]) == 89.28
            and gate["status"] == "passed" and not gate["blocking_issues"]
            and mission.get("status") == "founder_review"
            and mission.get("founder_approval_state") != "approved"
        )
        if not valid:
            raise ValidationError("Mission Zero approval constraints were not met.", error_code="MISSION_PACKAGE_CONSTRAINT_FAILED")
        content_hash = hashlib.sha256("\n".join(script["sections"]).encode("utf-8")).hexdigest()
        return MissionPackage(root=root, mission_id=script["mission_id"], mission_title=mission["title"],
            script_artifact_id=script["artifact_id"], parent_script_artifact_id=script["parent_artifact_id"],
            script_version=2, script_content_hash=content_hash, title=script["title"], sections=script["sections"],
            call_to_action=script["call_to_action"], estimated_duration_seconds=script["estimated_duration_seconds"],
            quality_score=gate["actual_score"], quality_gate=gate["status"], blocker_count=0)

    @staticmethod
    def _json(path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))
