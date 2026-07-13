import inspect

from app.main import (
    create_content_production_demo_app,
    create_intelligence_demo_app,
    create_local_render_demo_app,
    create_niche_discovery_demo_app,
)
from app.runtime.unified_context import DashboardContextStage
from company_missions.unified_dashboard import build_unified_dashboard_context


def test_unified_context_preserves_typed_cumulative_collections() -> None:
    context = build_unified_dashboard_context(
        DashboardContextStage.PRODUCTION
    )

    assert len(context.company_roster) == 24
    assert context.runtime_snapshot
    assert context.missions
    assert context.workflows
    assert context.decisions
    assert context.niche_discovery
    assert context.intelligence_package
    assert context.production_package
    assert context.render_result is None
    assert context.system_health
    assert context.activity_events


def test_specialized_factories_have_no_required_arguments() -> None:
    factories = (
        create_niche_discovery_demo_app,
        create_intelligence_demo_app,
        create_content_production_demo_app,
        create_local_render_demo_app,
    )
    for factory in factories:
        required = [
            parameter
            for parameter in inspect.signature(factory).parameters.values()
            if parameter.default is inspect.Parameter.empty
        ]
        assert required == []
