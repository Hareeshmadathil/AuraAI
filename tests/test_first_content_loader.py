"""Founder input loader safety tests."""

import json
from pathlib import Path

import pytest

from company_missions.first_real_content.loader import FounderInputLoader
from company_missions.first_real_content.dashboard import create_sample_first_content_input
from core import ValidationError


def test_loader_reads_valid_utf8_json(tmp_path: Path) -> None:
    path = tmp_path / "mission.json"
    path.write_text(json.dumps(create_sample_first_content_input().model_dump(mode="json")), encoding="utf-8")
    assert FounderInputLoader(tmp_path).load(Path("mission.json")).topic.startswith("Practical AI")


@pytest.mark.parametrize("name,content", [("missing.json", None), ("bad.json", "{")])
def test_loader_rejects_missing_or_invalid_json(tmp_path: Path, name: str, content: str | None) -> None:
    if content is not None:
        (tmp_path / name).write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError):
        FounderInputLoader(tmp_path).load(Path(name))


def test_loader_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="inside"):
        FounderInputLoader(tmp_path).load(Path("../outside.json"))
