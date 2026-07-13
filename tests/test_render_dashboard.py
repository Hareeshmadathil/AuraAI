from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from app.main import create_app, create_local_render_demo_app
from company_missions.local_render_pilot import (
    create_review_ready_production_package,
)
from core import utc_now
from production.rendering.models import (
    LocalRenderResult,
    RenderArtifactType,
    RenderEngine,
    RenderExportManifest,
    RenderSettings,
    RenderStatus,
)
from production.rendering.validation import completed_artifact


def test_empty_render_dashboard_and_unknown_artifact_are_safe() -> None:
    client = TestClient(create_app())
    page = client.get("/renders")
    assert page.status_code == 200
    assert "No local render supplied" in page.text
    assert client.get(f"/artifacts/{uuid4()}").status_code == 404


def test_local_render_demo_is_zero_argument_asgi_factory(monkeypatch) -> None:
    service = DashboardService(
        mode=DashboardMode.DEMO,
        data_label="LOCAL RENDER TEST",
    )
    monkeypatch.setattr(
        "company_missions.create_local_render_demo_dashboard_service",
        lambda result=None, package=None: service,
    )

    application = create_local_render_demo_app()

    assert application.state.dashboard_service is service
    assert TestClient(application).get("/renders").status_code == 200


def test_render_demo_preserves_full_company_and_prior_state(tmp_path: Path) -> None:
    package = create_review_ready_production_package()
    metadata_path = tmp_path / "review-artifact.json"
    metadata_path.write_text('{"review": true}', encoding="utf-8")
    artifact = completed_artifact(
        artifact_type=RenderArtifactType.RENDER_MANIFEST,
        path=metadata_path,
        mime_type="application/json",
        sample_data=True,
    )
    manifest = RenderExportManifest(
        production_package_id=package.package_id,
        render_engine=RenderEngine.DETERMINISTIC_GRAPHICS,
        settings=RenderSettings(output_root=tmp_path),
        capabilities=[],
        artifacts=[artifact],
        overall_status=RenderStatus.REVIEW_REQUIRED,
        completed_at=utc_now(),
    )
    render_result = LocalRenderResult(
        production_package_id=package.package_id,
        export_manifest=manifest,
        exported_artifacts=[artifact],
        dashboard_mode="test_review",
        completed_at=utc_now(),
    )
    client = TestClient(create_local_render_demo_app(render_result, package))
    data = client.get("/api/dashboard").json()
    employees_page = client.get("/employees").text

    assert "Aura" in employees_page
    assert "Orion" in employees_page
    assert "SEO Director" in employees_page
    assert "Script Writer" in employees_page
    assert len(data["executives"]) == 2
    assert len(data["directors"]) == 5
    assert len(data["specialists"]) == 17
    assert data["missions"]
    assert data["workflows"]
    assert data["recent_decisions"]
    assert data["niche_discovery"] is not None
    assert data["intelligence"] is not None
    assert data["production"] is not None
    assert len(data["render"]["artifacts"]) == 1
