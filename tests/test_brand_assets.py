"""Local, reviewable AuraAI brand asset tests."""

import json
from pathlib import Path
from xml.etree import ElementTree


BRAND_ROOT = Path("app/dashboard/static/brand")
CONCEPT_ASSETS = {
    f"{asset_type}-concept-{concept}.svg"
    for asset_type in ("logo", "wordmark", "app-icon")
    for concept in ("a", "b", "c")
}


def test_all_concept_svg_assets_are_accessible_local_vectors() -> None:
    """Require valid metadata and prohibit remote or raster content."""

    assert {path.name for path in BRAND_ROOT.glob("*-concept-*.svg")} == (
        CONCEPT_ASSETS
    )
    for name in CONCEPT_ASSETS:
        source = (BRAND_ROOT / name).read_text(encoding="utf-8")
        root = ElementTree.fromstring(source)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        assert root.tag.endswith("svg")
        assert root.find("svg:title", namespace) is not None
        assert root.find("svg:desc", namespace) is not None
        assert "<image" not in source
        assert "data:image" not in source
        assert "href=" not in source


def test_manifest_paths_and_review_status_are_valid() -> None:
    """Keep the manifest synchronized and every concept unapproved."""

    manifest = json.loads(
        (BRAND_ROOT / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["brand"] == "AuraAI"
    assert len(manifest["assets"]) == 9
    for asset in manifest["assets"]:
        assert asset["status"] == "concept"
        assert asset["review_required"] is True
        assert (BRAND_ROOT / asset["path"]).is_file()
        assert asset["accessibility_label"]


def test_icon_sprite_is_local_vector_geometry() -> None:
    """Provide every documented navigation and status symbol locally."""

    source = (BRAND_ROOT / "icons.svg").read_text(encoding="utf-8")
    root = ElementTree.fromstring(source)
    symbol_ids = {
        element.attrib["id"]
        for element in root
        if element.tag.endswith("symbol")
    }
    expected = {
        "command-center", "employees", "missions", "workflows",
        "decisions", "research", "intelligence", "marketing",
        "production", "creative-quality", "renders", "distribution",
        "analytics", "learning", "providers", "system",
        "founder-approval", "success", "warning", "blocked", "idle",
        "working", "completed",
    }
    assert expected <= symbol_ids
    assert "<image" not in source
