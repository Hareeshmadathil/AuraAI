"""README current-state and safety tests."""

from pathlib import Path
import re


def test_readme_opens_with_current_auraai_platform_description() -> None:
    """Present the current operating system before its legacy foundation."""

    source = Path("README.md").read_text(encoding="utf-8")
    opening = source[:500]

    assert source.startswith("# AuraAI\n")
    assert "founder-controlled AI media operating system" in opening
    assert "## Legacy Media Processing Foundation" in source
    assert source.index("## Legacy Media Processing Foundation") > source.index(
        "## Roadmap"
    )


def test_readme_is_safe_and_accurate_about_current_boundaries() -> None:
    """Avoid secret-shaped text, machine paths, and false integration claims."""

    source = Path("README.md").read_text(encoding="utf-8")
    normalized = " ".join(source.split())

    assert re.search(r"[A-Za-z]:\\", source) is None
    assert re.search(r"AIza[0-9A-Za-z_-]{20,}", source) is None
    assert "publishing remains manual" in normalized
    assert "Flow is not integrated" in normalized
    assert "Google AI Pro consumer access is separate" in normalized
    assert "dashboard is local and unauthenticated" in normalized.lower()
