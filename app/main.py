"""FastAPI application factory for the AuraAI dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.dashboard.routes import create_dashboard_router
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService


def create_app(
    dashboard_service: DashboardService | None = None,
    *,
    mode: DashboardMode | str = DashboardMode.EMPTY,
) -> FastAPI:
    """Create and configure the local AuraAI dashboard application.

    Args:
        dashboard_service: Optional explicitly configured state service.
        mode: Empty or demo state when no service is injected.

    Returns:
        Configured FastAPI application without external initialization.
    """

    dashboard_root = Path(__file__).resolve().parent / "dashboard"
    selected_mode = DashboardMode(mode)

    if dashboard_service is not None:
        service = dashboard_service
    elif selected_mode == DashboardMode.DEMO:
        from app.runtime.demo_state import create_demo_dashboard_service

        service = create_demo_dashboard_service()
    else:
        service = DashboardService(mode=selected_mode)

    application = FastAPI(
        title="AuraAI Dashboard",
        version="1.0.0",
        description="Local command-center interface for AuraAI.",
    )
    application.state.dashboard_service = service
    application.mount(
        "/static",
        StaticFiles(directory=dashboard_root / "static"),
        name="static",
    )
    application.include_router(
        create_dashboard_router(dashboard_root / "templates")
    )

    return application


def create_demo_app() -> FastAPI:
    """Create a dashboard application with explicit local sample data."""

    return create_app(mode=DashboardMode.DEMO)


def create_niche_discovery_demo_app() -> FastAPI:
    """Create the deterministic niche-discovery demonstration app."""

    from company_missions import (
        create_niche_discovery_demo_dashboard_service,
    )

    return create_app(
        dashboard_service=create_niche_discovery_demo_dashboard_service()
    )


def create_content_production_demo_app() -> FastAPI:
    """Create the deterministic Production v1 demonstration app."""

    from company_missions import (
        create_content_production_demo_dashboard_service,
    )

    return create_app(
        dashboard_service=create_content_production_demo_dashboard_service()
    )


def create_intelligence_demo_app() -> FastAPI:
    """Create the deterministic Intelligence Department demo app."""

    from company_missions import create_intelligence_demo_dashboard_service

    return create_app(
        dashboard_service=create_intelligence_demo_dashboard_service()
    )


def create_local_render_demo_app(
    local_render_result: object | None = None,
    production_package: object | None = None,
) -> FastAPI:
    """Create the local-render demo as a zero-argument Uvicorn factory.

    Optional arguments preserve the original injection-based calling style.
    """

    from company_missions import create_local_render_demo_dashboard_service

    return create_app(
        dashboard_service=create_local_render_demo_dashboard_service(
            local_render_result,
            production_package,
        )
    )


def create_creative_quality_demo_app() -> FastAPI:
    """Create the cumulative deterministic Creative Quality demo app."""

    from company_missions import create_creative_quality_demo_dashboard_service

    return create_app(
        dashboard_service=create_creative_quality_demo_dashboard_service()
    )


def create_quality_render_demo_app() -> FastAPI:
    """Create a quality-plus-existing-local-render review app."""

    from company_missions import create_quality_render_demo_dashboard_service

    return create_app(
        dashboard_service=create_quality_render_demo_dashboard_service()
    )


app = create_app()
