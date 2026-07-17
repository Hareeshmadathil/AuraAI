"""FastAPI application factory for the AuraAI dashboard."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.dashboard.routes import create_dashboard_router
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from production_research.service import ProductionResearchService
from mission_control.service import MissionControlService
from runtime_engine.runtime_manager import MissionRuntimeManager


def create_app(
    dashboard_service: DashboardService | None = None,
    *,
    mode: DashboardMode | str = DashboardMode.EMPTY,
    production_research_service: ProductionResearchService | None = None,
    mission_control_service: MissionControlService | None = None,
    runtime_manager: MissionRuntimeManager | None = None,
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
    if (
        runtime_manager is not None
        and runtime_manager.mission_control is not mission_control_service
    ):
        raise ValueError(
            "Runtime manager and dashboard must share Mission Control."
        )
    if (
        service.mission_control_service is not None
        and service.mission_control_service is not mission_control_service
    ):
        raise ValueError(
            "Dashboard service and application must share Mission Control."
        )
    application.state.mission_control_service = mission_control_service
    application.state.runtime_manager = runtime_manager
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


def create_runtime_app(
    *,
    database_path: Path | None = None,
    allowed_root: Path | None = None,
) -> FastAPI:
    """Create the normal local runtime dashboard with the canonical roster."""

    from app.runtime.composition import (
        DEFAULT_MISSION_CONTROL_DATABASE,
        create_runtime_application_services,
    )
    from config.settings import DATABASE_DIR

    services = create_runtime_application_services(
        database_path=database_path or DEFAULT_MISSION_CONTROL_DATABASE,
        allowed_root=allowed_root or DATABASE_DIR,
    )
    application = create_app(
        dashboard_service=services.dashboard_service,
        mission_control_service=services.mission_control_service,
        runtime_manager=services.runtime_manager,
    )
    application.state.runtime_services = services
    return application


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


def create_web_intelligence_demo_app() -> FastAPI:
    """Create a zero-argument offline web-intelligence dashboard."""
    return create_app(mode=DashboardMode.DEMO)


def create_intelligence_director_demo_app() -> FastAPI:
    """Create the zero-argument offline Intelligence Director dashboard."""
    return create_app(mode=DashboardMode.DEMO)


def create_knowledge_manager_demo_app() -> FastAPI:
    """Create the zero-argument in-memory Knowledge Manager dashboard."""
    return create_app(mode=DashboardMode.DEMO)


class LazyApplication:
    """ASGI wrapper preserving ``app`` without import-time startup."""

    def __init__(self, factory: Callable[[], FastAPI]) -> None:
        self._factory = factory
        self._application: FastAPI | None = None
        self._lock = Lock()

    @property
    def is_initialized(self) -> bool:
        """Return whether the ASGI application has been requested."""

        return self._application is not None

    def get_application(self) -> FastAPI:
        """Create the normal application once on first use."""

        if self._application is None:
            with self._lock:
                if self._application is None:
                    self._application = self._factory()
        return self._application

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        await self.get_application()(scope, receive, send)


app = LazyApplication(create_runtime_app)
