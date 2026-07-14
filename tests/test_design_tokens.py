"""Central AuraAI design-token contract tests."""

from pathlib import Path
import re


TOKENS = Path("app/dashboard/static/css/tokens.css")
DASHBOARD = Path("app/dashboard/static/css/dashboard.css")
TEMPLATES = Path("app/dashboard/templates")


def test_required_token_groups_exist() -> None:
    """Keep color, type, layout, focus, status, and department values central."""

    source = TOKENS.read_text(encoding="utf-8")
    required = (
        "--color-bg-canvas", "--color-brand-primary", "--color-text-primary",
        "--status-working", "--status-blocked", "--status-completed",
        "--department-executive", "--department-intelligence",
        "--department-production", "--department-analytics",
        "--font-display", "--font-body", "--font-mono", "--space-4",
        "--radius-lg", "--focus-ring", "--sidebar-width",
        "--layout-content-max", "--z-sidebar", "--data-1",
    )
    assert all(token in source for token in required)


def test_templates_do_not_hardcode_brand_colors() -> None:
    """Prevent presentation values from leaking into Jinja templates."""

    color_pattern = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}|rgba?\(")
    for template in TEMPLATES.glob("*.html"):
        assert color_pattern.search(template.read_text(encoding="utf-8")) is None


def test_dashboard_consumes_tokens_instead_of_brand_hex_values() -> None:
    """Keep component CSS token-driven and independently replaceable."""

    source = DASHBOARD.read_text(encoding="utf-8")
    assert "var(--color-brand-primary)" in source
    assert "var(--status-warning)" in source
    assert re.search(r"#[0-9a-fA-F]{3,8}", source) is None
