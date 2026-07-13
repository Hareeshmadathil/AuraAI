from pathlib import Path

from production.rendering.validation import sha256_file


def test_sha256_is_deterministic(tmp_path: Path) -> None:
    value = tmp_path / "artifact.txt"
    value.write_text("AuraAI local review", encoding="utf-8")
    assert sha256_file(value) == sha256_file(value)
    assert len(sha256_file(value)) == 64
