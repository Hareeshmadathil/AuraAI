"""FastAPI routes for the AuraAI local dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dashboard.brand_models import create_brand_review, status_label
from app.dashboard.models import DashboardSnapshot
from app.dashboard.service import DashboardService


def get_dashboard_service(request: Request) -> DashboardService:
    """Resolve the application-scoped dashboard service."""

    return request.app.state.dashboard_service


DashboardServiceDependency = Annotated[
    DashboardService,
    Depends(get_dashboard_service),
]


def create_dashboard_router(template_directory: Path) -> APIRouter:
    """Create dashboard routes using an explicit template directory."""

    router = APIRouter()
    templates = Jinja2Templates(directory=template_directory)
    templates.env.filters["status_label"] = status_label

    def render(
        *,
        request: Request,
        service: DashboardService,
        template_name: str,
        page_title: str,
        active_path: str,
        extra_context: dict[str, object] | None = None,
    ) -> HTMLResponse:
        """Render one page from a shared dashboard snapshot."""

        context: dict[str, object] = {
            "snapshot": service.build_snapshot(),
            "page_title": page_title,
            "active_path": active_path,
        }
        context.update(extra_context or {})
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

    @router.get("/", response_class=HTMLResponse)
    def dashboard_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the AuraAI command center."""

        return render(
            request=request,
            service=service,
            template_name="dashboard.html",
            page_title="Command Center",
            active_path="/",
        )

    @router.get("/employees", response_class=HTMLResponse)
    def employees_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the grouped company roster."""

        return render(
            request=request,
            service=service,
            template_name="employees.html",
            page_title="Employees",
            active_path="/employees",
        )

    @router.get("/brand", response_class=HTMLResponse)
    def brand_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic local brand concepts for founder review."""

        return render(
            request=request,
            service=service,
            template_name="brand.html",
            page_title="Brand System",
            active_path="/brand",
            extra_context={"brand_review": create_brand_review()},
        )

    @router.get("/missions", response_class=HTMLResponse)
    def missions_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render supplied missions or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title="Missions",
            active_path="/missions",
            extra_context={"collection_kind": "missions"},
        )

    @router.get("/workflows", response_class=HTMLResponse)
    def workflows_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render supplied workflows or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title="Workflows",
            active_path="/workflows",
            extra_context={"collection_kind": "workflows"},
        )

    @router.get("/decisions", response_class=HTMLResponse)
    def decisions_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render supplied decisions or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title="Decisions",
            active_path="/decisions",
            extra_context={"collection_kind": "decisions"},
        )

    @router.get("/system", response_class=HTMLResponse)
    def system_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render local system health information."""

        return render(
            request=request,
            service=service,
            template_name="system.html",
            page_title="System",
            active_path="/system",
        )

    @router.get("/production", response_class=HTMLResponse)
    def production_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the structured production package or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="production.html",
            page_title="Production",
            active_path="/production",
        )

    @router.get("/intelligence", response_class=HTMLResponse)
    def intelligence_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render all deterministic Intelligence reports."""

        return render(
            request=request,
            service=service,
            template_name="intelligence.html",
            page_title="Intelligence",
            active_path="/intelligence",
        )

    @router.get("/renders", response_class=HTMLResponse)
    def renders_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render local-review artifacts or a neutral empty state."""

        return render(
            request=request,
            service=service,
            template_name="renders.html",
            page_title="Renders",
            active_path="/renders",
        )

    @router.get("/creative-quality", response_class=HTMLResponse)
    def creative_quality_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic quality scores, gate, and revisions."""

        return render(
            request=request,
            service=service,
            template_name="creative_quality.html",
            page_title="Creative Quality",
            active_path="/creative-quality",
        )

    @router.get("/distribution", response_class=HTMLResponse)
    def distribution_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render local publish preparation and founder approval state."""

        return render(
            request=request,
            service=service,
            template_name="distribution.html",
            page_title="Distribution",
            active_path="/distribution",
        )

    @router.get("/analytics", response_class=HTMLResponse)
    def analytics_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render manually supplied metrics and calculated rates."""

        return render(
            request=request,
            service=service,
            template_name="analytics.html",
            page_title="Analytics",
            active_path="/analytics",
        )

    @router.get("/learning", response_class=HTMLResponse)
    def learning_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic learning recommendations."""

        return render(
            request=request,
            service=service,
            template_name="learning.html",
            page_title="Learning",
            active_path="/learning",
        )

    @router.get("/providers", response_class=HTMLResponse)
    def providers_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render provider availability, fallback, cache, and safe usage."""

        return render(
            request=request,
            service=service,
            template_name="providers.html",
            page_title="AI Providers",
            active_path="/providers",
        )

    @router.get("/mission-pilot", response_class=HTMLResponse)
    def mission_pilot_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the safe Real Content Pilot founder-review package."""

        return render(
            request=request,
            service=service,
            template_name="mission_pilot.html",
            page_title="Mission Pilot",
            active_path="/mission-pilot",
        )

    @router.get("/first-content-mission", response_class=HTMLResponse)
    def first_content_mission_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the first complete founder content-review package."""

        return render(
            request=request,
            service=service,
            template_name="first_content_mission.html",
            page_title="First Content Mission",
            active_path="/first-content-mission",
        )

    @router.get("/artifacts/{artifact_id}")
    def render_artifact(
        artifact_id: UUID,
        service: DashboardServiceDependency,
    ) -> FileResponse:
        """Serve a registered artifact ID; arbitrary paths are never accepted."""

        artifact = service.get_render_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Render artifact not found.")
        inline_types = {"video/mp4", "image/png", "image/jpeg"}
        return FileResponse(
            artifact.path,
            media_type=artifact.mime_type,
            filename=artifact.path.name,
            content_disposition_type=(
                "inline" if artifact.mime_type in inline_types else "attachment"
            ),
        )

    @router.get("/research", response_class=HTMLResponse)
    @router.get("/marketing", response_class=HTMLResponse)
    def placeholder_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render non-404 placeholders for planned dashboard sections."""

        section_name = request.url.path.removeprefix("/")
        title = section_name.title()
        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title=title,
            active_path=f"/{section_name}",
            extra_context={"collection_kind": "placeholder"},
        )

    @router.get("/health")
    def health(service: DashboardServiceDependency) -> dict[str, object]:
        """Report local web-service health as structured JSON."""

        system_health = service.build_snapshot().system_health
        return {
            "status": system_health.status.value,
            "service": "AuraAI Dashboard",
            "operational": system_health.web_service_operational,
            "test_status": system_health.test_status,
        }

    @router.get("/api/dashboard", response_model=DashboardSnapshot)
    def dashboard_api(
        service: DashboardServiceDependency,
    ) -> DashboardSnapshot:
        """Return the current dashboard snapshot as JSON."""

        return service.build_snapshot()

    return router
