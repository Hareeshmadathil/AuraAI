"""Local AuraAI brand review route tests."""

from fastapi.testclient import TestClient

from app.main import create_app, create_demo_app


def test_brand_page_displays_all_concepts_and_review_gate() -> None:
    """Render one deterministic founder-review page without runtime coupling."""

    response = TestClient(create_app()).get("/brand")

    assert response.status_code == 200
    assert "AuraAI Brand System" in response.text
    assert "Aura Orbit" in response.text
    assert "A Monogram" in response.text
    assert "Signal Core" in response.text
    assert "CONCEPT — FOUNDER REVIEW REQUIRED" in response.text
    assert "trademark" in response.text.lower()


def test_brand_navigation_is_additive_in_empty_and_demo_modes() -> None:
    """Preserve existing factories while exposing the same review route."""

    for application in (create_app(), create_demo_app()):
        client = TestClient(application)
        assert client.get("/").status_code == 200
        response = client.get("/brand")
        assert response.status_code == 200
        assert 'href="/brand"' in response.text
