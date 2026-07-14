"""Responsive dashboard and brand-review CSS tests."""

from pathlib import Path


def test_sidebar_and_content_reflow_across_supported_widths() -> None:
    """Keep desktop scrolling and mobile navigation accessible."""

    source = Path("app/dashboard/static/css/dashboard.css").read_text(
        encoding="utf-8"
    )

    assert "height: 100dvh" in source
    assert "overflow-y: auto" in source
    assert "overflow-x: hidden" in source
    assert "@media (max-width: 800px)" in source
    assert "@media (max-width: 520px)" in source
    assert ".content-shell { margin-left: 0; }" in source
    assert ".concept-grid { grid-template-columns: 1fr; }" in source


def test_grids_use_minmax_to_prevent_horizontal_overflow() -> None:
    """Allow concept and component cards to shrink before wrapping."""

    source = Path("app/dashboard/static/css/dashboard.css").read_text(
        encoding="utf-8"
    )

    assert ".concept-grid" in source
    assert "repeat(3, minmax(0, 1fr))" in source
    assert ".component-showcase" in source
    assert "min-width: 0" in source
