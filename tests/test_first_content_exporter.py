"""Safe explicit export tests."""

import hashlib
import json
from pathlib import Path

import pytest

from company_missions.first_real_content.dashboard import create_sample_first_content_input
from company_missions.first_real_content.exporter import FirstContentMissionExporter
from company_missions.first_real_content.runner import FirstRealContentMissionRunner
from core import ValidationError


def test_exporter_writes_structure_and_valid_checksums(tmp_path: Path) -> None:
    result = FirstRealContentMissionRunner().run_typed(create_sample_first_content_input())
    target, manifest = FirstContentMissionExporter(tmp_path).export(result)
    required = [
        "mission/mission.json", "research/research.json", "seo/seo.json",
        "script/script-v1.md", "quality/creative-quality.json",
        "production/production-package.json", "founder-review/review-package.json",
        "manifest/artifact-manifest.json", "manifest/sha256.json",
    ]
    assert all((target / item).is_file() for item in required)
    checksums = json.loads((target / "manifest/sha256.json").read_text(encoding="utf-8"))
    first = manifest.artifacts[0]
    assert checksums[first.relative_path] == hashlib.sha256((target / first.relative_path).read_bytes()).hexdigest()
    text = "\n".join(path.read_text(encoding="utf-8") for path in target.rglob("*.*"))
    assert "api_key" not in text.lower()
    assert "raw_response" not in text.lower()


def test_exporter_prevents_overwrite(tmp_path: Path) -> None:
    result = FirstRealContentMissionRunner().run_typed(create_sample_first_content_input())
    exporter = FirstContentMissionExporter(tmp_path)
    exporter.export(result)
    with pytest.raises(ValidationError) as caught:
        exporter.export(result)
    assert caught.value.error_code == "MISSION_EXPORT_EXISTS"
