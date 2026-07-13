"""Typed cumulative context for every specialized AuraAI dashboard."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from app.dashboard.models import (
    ActivityEventSummary,
    DashboardMode,
    SystemHealthSummary,
)
from app.dashboard.service import DashboardService
from core import AgentIdentity, AuraBaseModel, DecisionRecord
from intelligence.models import IntelligencePackage
from creative_quality.models import CreativeQualityPackage
from analytics.models import AnalyticsReport, LearningReport
from distribution.models import DistributionPackage
from production.models import ProductionPackage
from production.rendering.models import LocalRenderResult
from runtime_engine.dashboard_adapter import create_dashboard_service_from_runtime
from runtime_engine.models import (
    RuntimeMissionState,
    RuntimeSnapshot,
    RuntimeWorkflowState,
    RuntimeCreativeQualityState,
)


class DashboardContextStage(StrEnum):
    """Highest completed stage represented by a unified context."""

    NICHE_DISCOVERY = "niche_discovery"
    INTELLIGENCE = "intelligence"
    PRODUCTION = "production"
    RENDER = "render"
    CREATIVE_QUALITY = "creative_quality"
    QUALITY_RENDER = "quality_render"
    DISTRIBUTION = "distribution"
    ANALYTICS = "analytics"
    LEARNING = "learning"


class UnifiedDashboardContext(AuraBaseModel):
    """One immutable-style cumulative source for dashboard composition."""

    stage: DashboardContextStage
    mode: DashboardMode = DashboardMode.DEMO
    data_label: str = Field(min_length=1, max_length=500)
    company_roster: list[AgentIdentity] = Field(min_length=1)
    runtime_snapshot: RuntimeSnapshot
    missions: list[RuntimeMissionState] = Field(default_factory=list)
    workflows: list[RuntimeWorkflowState] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    intelligence_package: IntelligencePackage | None = None
    production_package: ProductionPackage | None = None
    render_result: LocalRenderResult | None = None
    creative_quality_package: CreativeQualityPackage | None = None
    quality_runtime_state: RuntimeCreativeQualityState | None = None
    quality_labels: list[str] = Field(default_factory=list)
    distribution_package: DistributionPackage | None = None
    analytics_report: AnalyticsReport | None = None
    learning_report: LearningReport | None = None
    system_health: SystemHealthSummary
    activity_events: list[ActivityEventSummary] = Field(default_factory=list)
    niche_discovery: dict[str, Any] | None = None
    data_sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cumulative_state(self) -> "UnifiedDashboardContext":
        """Reject a later stage that omits its required earlier payloads."""

        if self.stage in {
            DashboardContextStage.INTELLIGENCE,
            DashboardContextStage.PRODUCTION,
            DashboardContextStage.RENDER,
            DashboardContextStage.CREATIVE_QUALITY,
            DashboardContextStage.QUALITY_RENDER,
            DashboardContextStage.DISTRIBUTION,
            DashboardContextStage.ANALYTICS,
            DashboardContextStage.LEARNING,
        } and self.intelligence_package is None:
            raise ValueError("Intelligence payload is required for this stage.")
        if self.stage in {
            DashboardContextStage.PRODUCTION,
            DashboardContextStage.RENDER,
            DashboardContextStage.CREATIVE_QUALITY,
            DashboardContextStage.QUALITY_RENDER,
            DashboardContextStage.DISTRIBUTION,
            DashboardContextStage.ANALYTICS,
            DashboardContextStage.LEARNING,
        } and self.production_package is None:
            raise ValueError("Production payload is required for this stage.")
        if self.stage == DashboardContextStage.RENDER and self.render_result is None:
            raise ValueError("Render payload is required for the render stage.")
        if self.stage in {
            DashboardContextStage.CREATIVE_QUALITY,
            DashboardContextStage.QUALITY_RENDER,
            DashboardContextStage.DISTRIBUTION,
            DashboardContextStage.ANALYTICS,
            DashboardContextStage.LEARNING,
        } and self.creative_quality_package is None:
            raise ValueError("Creative Quality payload is required for this stage.")
        if self.stage in {
            DashboardContextStage.DISTRIBUTION,
            DashboardContextStage.ANALYTICS,
            DashboardContextStage.LEARNING,
        } and self.distribution_package is None:
            raise ValueError("Distribution payload is required for this stage.")
        if self.stage in {
            DashboardContextStage.ANALYTICS,
            DashboardContextStage.LEARNING,
        } and self.analytics_report is None:
            raise ValueError("Analytics payload is required for this stage.")
        if (
            self.stage == DashboardContextStage.LEARNING
            and self.learning_report is None
        ):
            raise ValueError("Learning payload is required for this stage.")
        if (
            self.stage == DashboardContextStage.QUALITY_RENDER
            and self.render_result is None
        ):
            raise ValueError("Render payload is required for quality-render stage.")
        return self

    def create_dashboard_service(self) -> DashboardService:
        """Adapt this context through the shared dashboard dependency boundary."""

        return create_dashboard_service_from_runtime(
            self.runtime_snapshot,
            mode=self.mode,
            data_label=self.data_label,
            production_package=self.production_package,
            intelligence_package=self.intelligence_package,
            local_render_result=self.render_result,
            company_roster=self.company_roster,
            niche_discovery=self.niche_discovery,
            creative_quality_package=self.creative_quality_package,
            distribution_package=self.distribution_package,
            analytics_report=self.analytics_report,
            learning_report=self.learning_report,
        )
