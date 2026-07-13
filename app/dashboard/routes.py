"""FastAPI routes for the AuraAI local dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
