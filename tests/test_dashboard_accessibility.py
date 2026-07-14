"""Static accessibility safeguards for the AuraAI dashboard shell."""

from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_shell_has_landmarks_skip_link_and_labelled_navigation() -> None:
    """Keep keyboard and screen-reader structure visible on every page."""

    response = TestClient(create_app()).get("/brand")

    assert 'class="skip-link"' in response.text
    assert 'href="#main-content"' in response.text
    assert '<main id="main-content">' in response.text
    assert 'aria-label="Primary navigation"' in response.text
    assert 'aria-current="page"' in response.text


def test_focus_and_reduced_motion_rules_exist() -> None:
    """Preserve visible keyboard focus and user motion preferences."""

    source = Path("app/dashboard/static/css/dashboard.css").read_text(
        encoding="utf-8"
    )

    assert ":focus-visible" in source
    assert "outline: var(--focus-ring)" in source
    assert "@media (prefers-reduced-motion: reduce)" in source


def test_logo_concepts_have_svg_title_and_description() -> None:
    """Expose an accessible name and description in every logo proposal."""

    for path in Path("app/dashboard/static/brand").glob("*-concept-*.svg"):
        root = ElementTree.parse(path).getroot()
        children = list(root)
        assert any(child.tag.endswith("title") for child in children)
        assert any(child.tag.endswith("desc") for child in children)
