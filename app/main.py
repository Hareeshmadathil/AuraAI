"""FastAPI application factory for the AuraAI dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.dashboard.routes import create_dashboard_router
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from production_research.service import ProductionResearchService


def create_app(
    dashboard_service: DashboardService | None = None,
    *,
    mode: DashboardMode | str = DashboardMode.EMPTY,
    production_research_service: ProductionResearchService | None = None,
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
    application.state.production_research_service = (
        production_research_service or ProductionResearchService()
    )
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


def create_distribution_demo_app() -> FastAPI:
    """Create the cumulative local Distribution and Analytics demo."""

    from company_missions import create_distribution_demo_dashboard_service

    return create_app(
        dashboard_service=create_distribution_demo_dashboard_service()
    )


def create_real_content_pilot_demo_app() -> FastAPI:
    """Create the cumulative offline pilot at its founder-review gate."""

    from company_missions import create_real_content_pilot_demo_dashboard_service

    return create_app(
        dashboard_service=create_real_content_pilot_demo_dashboard_service()
    )


def create_first_content_mission_demo_app() -> FastAPI:
    """Create the cumulative deterministic first-content review app."""

    from company_missions.first_real_content.dashboard import (
        create_first_content_mission_demo_dashboard_service,
    )

    return create_app(
        dashboard_service=create_first_content_mission_demo_dashboard_service()
    )


def create_private_video_production_demo_app() -> FastAPI:
    """Create a zero-argument planning-only private video demo app."""

    from private_video_production.dashboard import (
        create_private_video_production_demo_dashboard_service,
    )

    return create_app(
        dashboard_service=create_private_video_production_demo_dashboard_service()
    )


def create_production_connector_demo_app() -> FastAPI:
    """Create the deterministic offline production-connector dashboard."""
    return create_app(mode=DashboardMode.DEMO)


app = create_app()
