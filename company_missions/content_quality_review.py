"""Company-mission adapters for deterministic Creative Quality review."""

from __future__ import annotations

from app.dashboard.service import DashboardService
from app.runtime.unified_context import DashboardContextStage
from core import OperationResult
from creative_quality.pipeline import (
    CreativeQualityPipeline,
    create_creative_quality_pipeline,
)
from production.models import ProductionPackage
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.state_manager import RuntimeStateManager


class ContentQualityMission:
    """Run the additive pre-render quality stage for one production package."""

    def __init__(self, pipeline: CreativeQualityPipeline) -> None:
        self.pipeline = pipeline

    def run(
        self,
        package: ProductionPackage,
        *,
        founder_quality_override: bool = False,
    ) -> OperationResult:
        """Return the pipeline's structured review or blocker state."""

        return self.pipeline.run(
            package,
            founder_quality_override=founder_quality_override,
        )


def create_content_quality_pipeline(
    *,
    state_manager: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
    minimum_score: float = 75.0,
) -> CreativeQualityPipeline:
    """Create an isolated offline company quality pipeline."""

    return create_creative_quality_pipeline(
        state_manager=state_manager,
        event_bus=event_bus,
        minimum_score=minimum_score,
    )


def create_creative_quality_demo_dashboard_service() -> DashboardService:
    """Build cumulative Research through Creative Quality demo state."""

    from company_missions.unified_dashboard import create_unified_dashboard_service

    return create_unified_dashboard_service(DashboardContextStage.CREATIVE_QUALITY)


def create_quality_render_demo_dashboard_service() -> DashboardService:
    """Combine quality state with a validated existing local render."""

    from company_missions.unified_dashboard import create_unified_dashboard_service

    return create_unified_dashboard_service(DashboardContextStage.QUALITY_RENDER)
