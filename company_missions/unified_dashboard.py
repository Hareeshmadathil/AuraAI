"""Cumulative orchestration for specialized dashboard demo factories."""

from __future__ import annotations

from pathlib import Path

from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from app.runtime.company_roster import create_company_roster
from app.runtime.unified_context import (
    DashboardContextStage,
    UnifiedDashboardContext,
)
from company_missions.content_production import (
    ContentProductionMission,
    create_content_production_pipeline,
)
from company_missions.fixtures import create_sample_niche_discovery_input
from company_missions.local_render_pilot import (
    _default_render_output_root,
    load_latest_local_render_demo,
)
from company_missions.models import NicheDiscoveryResult
from company_missions.niche_discovery import create_niche_discovery_pipeline
from intelligence.models import IntelligencePackage
from intelligence.pipeline import create_intelligence_pipeline
from creative_quality.models import (
    CreativeQualityPackage,
    CreativeQualityPipelineResult,
)
from creative_quality.pipeline import create_creative_quality_pipeline
from analytics.models import AnalyticsReport, LearningReport, ManualPerformanceMetrics
from analytics.pipeline import create_analytics_pipelines
from distribution.approval import DistributionApprovalService
from distribution.models import DistributionChannel, DistributionPackage
from distribution.pipeline import create_distribution_pipeline
from production.models import ProductionPackage, ProductionPipelineResult
from production.rendering.models import LocalRenderResult
from runtime_engine.dashboard_adapter import (
    build_activity_summaries,
    build_system_health_summary,
)


def build_unified_dashboard_context(
    stage: DashboardContextStage,
    *,
    render_result: LocalRenderResult | None = None,
    production_package: ProductionPackage | None = None,
    output_root: Path | None = None,
    creative_quality_package: CreativeQualityPackage | None = None,
) -> UnifiedDashboardContext:
    """Run cumulative in-memory stages and reuse existing render artifacts."""

    if (render_result is None) != (production_package is None):
        raise ValueError(
            "Render result and production package must be supplied together."
        )
    roster = create_company_roster()
    niche_pipeline, orchestrator = create_niche_discovery_pipeline()
    niche_operation = niche_pipeline.run(
        create_sample_niche_discovery_input(),
        user_confirmed=True,
    )
    if not niche_operation.success:
        raise RuntimeError(niche_operation.message)
    niche_result = NicheDiscoveryResult.model_validate(
        niche_operation.data["niche_discovery_result"]
    )
    state = orchestrator.state_manager
    bus = orchestrator.event_bus
    intelligence_package: IntelligencePackage | None = None
    generated_production: ProductionPackage | None = None

    if stage != DashboardContextStage.NICHE_DISCOVERY:
        intelligence_pipeline = create_intelligence_pipeline(
            state_manager=state,
            event_bus=bus,
        )
        intelligence_operation = intelligence_pipeline.run(niche_result)
        if not intelligence_operation.success:
            raise RuntimeError(intelligence_operation.message)
        intelligence_package = IntelligencePackage.model_validate(
            intelligence_operation.data["intelligence_package"]
        )

    if stage in {
        DashboardContextStage.PRODUCTION,
        DashboardContextStage.RENDER,
        DashboardContextStage.CREATIVE_QUALITY,
        DashboardContextStage.QUALITY_RENDER,
        DashboardContextStage.DISTRIBUTION,
        DashboardContextStage.ANALYTICS,
        DashboardContextStage.LEARNING,
    }:
        production_pipeline, _ = create_content_production_pipeline(
            state_manager=state,
            event_bus=bus,
        )
        production_operation = ContentProductionMission(
            production_pipeline
        ).run(
            intelligence_package,
            founder_approved=False,
        )
        if not production_operation.success:
            raise RuntimeError(production_operation.message)
        generated_production = ProductionPipelineResult.model_validate(
            production_operation.data["production_pipeline_result"]
        ).package

    if stage in {
        DashboardContextStage.RENDER,
        DashboardContextStage.QUALITY_RENDER,
        DashboardContextStage.DISTRIBUTION,
        DashboardContextStage.ANALYTICS,
        DashboardContextStage.LEARNING,
    } and render_result is None:
        root = (output_root or _default_render_output_root()).resolve()
        loaded = load_latest_local_render_demo(root)
        if loaded is None:
            raise RuntimeError(
                "No valid local render exists. Run the explicit render pilot first."
            )
        render_result, production_package = loaded
    selected_production = production_package or generated_production
    if selected_production is None and stage in {
        DashboardContextStage.CREATIVE_QUALITY,
        DashboardContextStage.QUALITY_RENDER,
        DashboardContextStage.DISTRIBUTION,
        DashboardContextStage.ANALYTICS,
        DashboardContextStage.LEARNING,
    }:
        raise RuntimeError("Creative Quality requires a production package.")
    if stage in {
        DashboardContextStage.CREATIVE_QUALITY,
        DashboardContextStage.QUALITY_RENDER,
        DashboardContextStage.DISTRIBUTION,
        DashboardContextStage.ANALYTICS,
        DashboardContextStage.LEARNING,
    } and creative_quality_package is None:
        quality_pipeline = create_creative_quality_pipeline(
            state_manager=state,
            event_bus=bus,
        )
        quality_operation = quality_pipeline.run(selected_production)
        result_data = quality_operation.data.get(
            "creative_quality_pipeline_result"
        )
        if result_data is None:
            raise RuntimeError(quality_operation.message)
        creative_quality_package = CreativeQualityPipelineResult.model_validate(
            result_data
        ).quality_package
    elif creative_quality_package is not None:
        if (
            selected_production is None
            or creative_quality_package.production_package_id
            != selected_production.package_id
        ):
            raise ValueError(
                "Creative Quality package must match the selected production package."
            )
        state.register_creative_quality_package(
            creative_quality_package,
            replace=True,
        )
    distribution_package: DistributionPackage | None = None
    analytics_report: AnalyticsReport | None = None
    learning_report: LearningReport | None = None
    if stage in {
        DashboardContextStage.DISTRIBUTION,
        DashboardContextStage.ANALYTICS,
        DashboardContextStage.LEARNING,
    }:
        distribution_pipeline = create_distribution_pipeline(
            state_manager=state,
            event_bus=bus,
        )
        distribution_operation = distribution_pipeline.run(
            creative_quality_package
        )
        if not distribution_operation.success:
            raise RuntimeError(distribution_operation.message)
        distribution_package = DistributionPackage.model_validate(
            distribution_operation.data["distribution_package"]
        )
    if stage in {
        DashboardContextStage.ANALYTICS,
        DashboardContextStage.LEARNING,
    }:
        approval = DistributionApprovalService(
            state_manager=state,
            event_bus=bus,
        )
        required_keys = {
            item.key
            for item in distribution_package.manual_approval_checklist.items
            if item.required
        }
        distribution_package = approval.approve(
            distribution_package,
            founder_name="Demo Founder",
            approval_note="Deterministic demo approval; no upload was performed.",
            confirmed_checklist_keys=required_keys,
        )
        distribution_package = approval.mark_ready_to_upload(
            distribution_package
        )
        distribution_package = approval.confirm_manual_upload(
            distribution_package,
            founder_confirmed=True,
        )
        metrics = ManualPerformanceMetrics(
            distribution_package_id=distribution_package.package_id,
            platform=DistributionChannel.YOUTUBE,
            views=1000,
            click_through_rate=5.2,
            average_view_duration_seconds=126,
            retention_percentage=52,
            watch_time_hours=35,
            likes=80,
            comments=12,
            shares=9,
            subscribers_gained=18,
            impressions=19_231,
            traffic_sources={"browse": 600, "search": 300, "external": 100},
            countries={"India": 450, "United States": 350, "Other": 200},
            devices={"mobile": 700, "desktop": 250, "tv": 50},
            returning_viewers=280,
            new_viewers=720,
            upload_hour_utc=14,
        )
        analytics_pipeline, learning_pipeline = create_analytics_pipelines(
            state_manager=state,
            event_bus=bus,
        )
        analytics_operation = analytics_pipeline.run(
            distribution_package,
            metrics,
        )
        if not analytics_operation.success:
            raise RuntimeError(analytics_operation.message)
        analytics_report = AnalyticsReport.model_validate(
            analytics_operation.data["analytics_report"]
        )
        distribution_package = DistributionPackage.model_validate(
            analytics_operation.data["distribution_package"]
        )
        if stage == DashboardContextStage.LEARNING:
            learning_operation = learning_pipeline.run(
                distribution_package,
                analytics_report,
            )
            if not learning_operation.success:
                raise RuntimeError(learning_operation.message)
            learning_report = LearningReport.model_validate(
                learning_operation.data["learning_report"]
            )
    snapshot = state.snapshot()
    return UnifiedDashboardContext(
        stage=stage,
        mode=DashboardMode.DEMO,
        data_label=_data_label(stage),
        company_roster=[employee.identity for employee in roster.employees],
        runtime_snapshot=snapshot,
        missions=snapshot.missions,
        workflows=snapshot.workflows,
        decisions=snapshot.decisions,
        intelligence_package=intelligence_package,
        production_package=selected_production,
        render_result=render_result,
        creative_quality_package=creative_quality_package,
        quality_runtime_state=(
            snapshot.creative_quality_packages[-1]
            if snapshot.creative_quality_packages
            else None
        ),
        quality_labels=(
            [
                "DETERMINISTIC HEURISTIC",
                "FOUNDER REVIEW SEPARATE",
                "NOT PUBLISHING APPROVAL",
            ]
            if creative_quality_package is not None
            else []
        ),
        distribution_package=distribution_package,
        analytics_report=analytics_report,
        learning_report=learning_report,
        system_health=build_system_health_summary(snapshot),
        activity_events=build_activity_summaries(snapshot),
        niche_discovery=niche_result.model_dump(mode="json"),
        data_sources=_data_sources(
            intelligence_package=intelligence_package,
            production_package=selected_production,
            render_result=render_result,
            creative_quality_package=creative_quality_package,
            distribution_package=distribution_package,
            analytics_report=analytics_report,
            learning_report=learning_report,
        ),
    )


def create_unified_dashboard_service(
    stage: DashboardContextStage,
    *,
    render_result: LocalRenderResult | None = None,
    production_package: ProductionPackage | None = None,
    output_root: Path | None = None,
    creative_quality_package: CreativeQualityPackage | None = None,
) -> DashboardService:
    """Create the injected service consumed by a specialized app factory."""

    return build_unified_dashboard_context(
        stage,
        render_result=render_result,
        production_package=production_package,
        output_root=output_root,
        creative_quality_package=creative_quality_package,
    ).create_dashboard_service()


def _data_sources(
    *,
    intelligence_package: IntelligencePackage | None,
    production_package: ProductionPackage | None,
    render_result: LocalRenderResult | None,
    creative_quality_package: CreativeQualityPackage | None,
    distribution_package: DistributionPackage | None = None,
    analytics_report: AnalyticsReport | None = None,
    learning_report: LearningReport | None = None,
) -> list[str]:
    values = ["deterministic_niche_discovery"]
    if intelligence_package is not None:
        values.append("deterministic_intelligence")
    if production_package is not None:
        values.append("deterministic_production")
    if render_result is not None:
        values.append("validated_local_render_manifest")
    if creative_quality_package is not None:
        values.append("deterministic_creative_quality_heuristics")
    if distribution_package is not None:
        values.append("local_distribution_preparation")
    if analytics_report is not None:
        values.append("founder_supplied_demo_metrics")
    if learning_report is not None:
        values.append("deterministic_performance_learning")
    return values


def _data_label(stage: DashboardContextStage) -> str:
    return {
        DashboardContextStage.NICHE_DISCOVERY: (
            "NICHE DISCOVERY DEMO / DETERMINISTIC SAMPLE DATA / "
            "UNIFIED CONTEXT"
        ),
        DashboardContextStage.INTELLIGENCE: (
            "RESEARCH + INTELLIGENCE / UNIFIED DETERMINISTIC DEMO"
        ),
        DashboardContextStage.PRODUCTION: (
            "RESEARCH + INTELLIGENCE + PRODUCTION / UNIFIED DEMO"
        ),
        DashboardContextStage.RENDER: (
            "FULL LOCAL REVIEW CONTEXT / NOT PUBLISHED"
        ),
        DashboardContextStage.CREATIVE_QUALITY: (
            "CREATIVE QUALITY DEMO / DETERMINISTIC HEURISTICS / "
            "FOUNDER REVIEW SEPARATE"
        ),
        DashboardContextStage.QUALITY_RENDER: (
            "QUALITY + LOCAL RENDER REVIEW / NOT PUBLISHED"
        ),
        DashboardContextStage.DISTRIBUTION: (
            "DISTRIBUTION REVIEW / LOCAL ONLY / NOT PUBLISHED"
        ),
        DashboardContextStage.ANALYTICS: (
            "MANUALLY SUPPLIED ANALYTICS / DEMO DATA / LOCAL ONLY"
        ),
        DashboardContextStage.LEARNING: (
            "DISTRIBUTION + ANALYTICS + DETERMINISTIC LEARNING / DEMO"
        ),
    }[stage]
