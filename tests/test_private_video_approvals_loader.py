"""Approval and approved-package loading tests."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from core import ValidationError
from private_video_production.approvals import PrivateVideoApprovalService
from private_video_production.loader import MissionZeroPackageLoader
from private_video_production.models import PrivateVideoApproval


PACKAGE = Path("outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a")


def test_loads_exact_approved_mission_zero_package(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)

    assert value.script_version == 2
    assert value.quality_score == 89.28
    assert value.blocker_count == 0
    assert value.rendered is False
    assert value.published is False
    assert len(value.script_content_hash) == 64


def test_loader_rejects_missing_script_v2_without_fallback(tmp_path: Path) -> None:
    target = tmp_path / "package"
    shutil.copytree(PACKAGE, target)
    (target / "script/script-v2.json").unlink()

    with pytest.raises(ValidationError, match="script/script-v2.json"):
        MissionZeroPackageLoader().load(target, tmp_path / "out")


def test_loader_rejects_altered_script_hash(tmp_path: Path) -> None:
    target = tmp_path / "package"
    shutil.copytree(PACKAGE, target)
    script = target / "script/script-v2.json"
    script.write_text(script.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        MissionZeroPackageLoader().load(target, tmp_path / "out")
    assert caught.value.error_code == "SCRIPT_CONTENT_HASH_MISMATCH"


def test_loader_rejects_failed_gate_and_blockers(tmp_path: Path) -> None:
    target = tmp_path / "package"
    shutil.copytree(PACKAGE, target)
    quality_path = target / "quality/revised/creative-quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["gate"]["status"] = "blocked"
    quality_path.write_text(json.dumps(quality), encoding="utf-8")

    with pytest.raises(ValidationError, match="gate"):
        MissionZeroPackageLoader().load(target, tmp_path / "out")


def test_loader_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="traversal"):
        MissionZeroPackageLoader._load_json(tmp_path, "../outside.json")


def test_approval_boundaries_are_independent_and_content_bound(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    service = PrivateVideoApprovalService()
    content_only = service.record(
        value,
        content_approved=True,
        private_render_approved=False,
        founder_confirmed=True,
    )

    service.require_content(content_only, value)
    with pytest.raises(ValidationError) as caught:
        service.require_private_render(content_only, value)
    assert caught.value.error_code == "PRIVATE_RENDER_APPROVAL_REQUIRED"
    assert content_only.publishing_approved is False
    assert PrivateVideoApproval.model_validate_json(content_only.model_dump_json()) == content_only


def test_approval_requires_confirmation_and_rejects_publish(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    with pytest.raises(ValidationError) as caught:
        PrivateVideoApprovalService().record(
            value,
            content_approved=True,
            private_render_approved=False,
            founder_confirmed=False,
        )
    assert caught.value.error_code == "FOUNDER_CONFIRMATION_REQUIRED"
    with pytest.raises(PydanticValidationError):
        PrivateVideoApproval(
            mission_id=value.mission_id,
            script_artifact_id=value.script_artifact_id,
            script_version=2,
            content_approved=True,
            private_render_approved=True,
            publishing_approved=True,
            content_hash=value.script_content_hash,
        )
