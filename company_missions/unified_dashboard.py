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
    }:
        raise RuntimeError("Creative Quality requires a production package.")
    if stage in {
        DashboardContextStage.CREATIVE_QUALITY,
        DashboardContextStage.QUALITY_RENDER,
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
        system_health=build_system_health_summary(snapshot),
        activity_events=build_activity_summaries(snapshot),
        niche_discovery=niche_result.model_dump(mode="json"),
        data_sources=_data_sources(
            intelligence_package=intelligence_package,
            production_package=selected_production,
            render_result=render_result,
            creative_quality_package=creative_quality_package,
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
    }[stage]
