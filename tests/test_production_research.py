"""Focused tests for the isolated AI Production Research department."""

from __future__ import annotations

import json
import socket
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from production_research import (
    PricingModel,
    ProductionResearchService,
    ProviderCategory,
    ProviderScorer,
)
from production_research.cli import main
from production_research.reporting import ProductionResearchReporter


def test_catalog_covers_every_required_provider_category() -> None:
    service = ProductionResearchService()
    providers = service.list_providers()

    assert {provider.category for provider in providers} == set(ProviderCategory)
    assert all(provider.name for provider in providers)
    assert all(provider.website for provider in providers)
    assert all(0 <= provider.local_score <= 100 for provider in providers)
    assert all(provider.placeholder_data is True for provider in providers)


def test_scoring_is_deterministic_and_penalizes_more_weaknesses() -> None:
    values = {
        "api_available": True,
        "free_tier_available": True,
        "trial_available": True,
        "commercial_license_notes": "Founder review required.",
        "pricing_model": PricingModel.USAGE_BASED,
        "strengths": ["Typed API", "Local validation"],
    }

    first = ProviderScorer.score_fields(**values, weaknesses=["Manual review"])
    second = ProviderScorer.score_fields(**values, weaknesses=["Manual review"])
    weaker = ProviderScorer.score_fields(
        **values,
        weaknesses=["Manual review", "Unverified pricing", "Limited controls"],
    )

    assert first == second
    assert weaker < first


def test_report_contains_ranked_summaries_and_no_network_claim() -> None:
    report = ProductionResearchService().build_report()

    assert report.department_name == "AI Production Research"
    assert report.network_requests_performed is False
    assert len(report.categories) == 7
    assert all(summary.provider_count >= 1 for summary in report.categories)
    assert "PLACEHOLDER" in report.data_notice


def test_json_and_markdown_exports_are_valid(tmp_path: Path) -> None:
    report = ProductionResearchService().build_report()
    json_path, markdown_path = ProductionResearchReporter().export(report, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["network_requests_performed"] is False
    assert len(payload["providers"]) == 7
    assert "# AI Production Research" in markdown
    assert "## Category summary" in markdown
    assert "Windows SAPI Local Voice" in markdown


def test_cli_lists_categories_and_providers(capsys) -> None:
    assert main(["--list-categories"]) == 0
    categories = capsys.readouterr().out
    assert "voice" in categories
    assert "research_model" in categories

    assert main(["--list-providers"]) == 0
    providers = capsys.readouterr().out
    assert "Windows SAPI Local Voice | voice" in providers
    assert "Research Model Candidate A | research_model" in providers


def test_cli_shows_one_provider_and_exports(tmp_path: Path, capsys) -> None:
    assert main(["--show-provider", "Windows SAPI Local Voice"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["category"] == "voice"
    assert payload["status"] == "approved"

    assert main(["--export-report", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "production-research-report.json" in output
    assert "production-research-report.md" in output
    assert (tmp_path / "production-research-report.json").is_file()


def test_cli_default_displays_help_without_side_effects(capsys) -> None:
    assert main([]) == 0
    assert "--list-categories" in capsys.readouterr().out


def test_department_service_performs_no_network_requests(monkeypatch) -> None:
    def reject_network(*args, **kwargs):
        raise AssertionError("Production research must remain offline.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    report = ProductionResearchService().build_report()

    assert report.providers
    assert report.network_requests_performed is False


def test_dashboard_page_is_local_and_api_remains_backward_compatible() -> None:
    client = TestClient(create_app())

    page = client.get("/production-research")
    payload = client.get("/api/dashboard").json()
    assert page.status_code == 200
    assert "AI Production Research" in page.text
    assert "PLACEHOLDER / MANUALLY MAINTAINED DATA" in page.text
    assert "Video Generator" in page.text
    assert "production_research" not in payload


def test_injected_dashboard_research_service_is_used() -> None:
    service = ProductionResearchService()
    application = create_app(production_research_service=service)

    assert application.state.production_research_service is service
    assert TestClient(application).get("/production-research").status_code == 200
