"""Cumulative dashboard composition for the deterministic pilot."""

from app.dashboard.models import ActivityEventSummary, ActivityEventType
from app.dashboard.service import DashboardService
from app.runtime.unified_context import DashboardContextStage
from company_missions.unified_dashboard import build_unified_dashboard_context

from company_missions.real_content_pilot.fixtures import (
    run_deterministic_real_content_pilot,
)


def create_real_content_pilot_demo_dashboard_service() -> DashboardService:
    """Preserve prior company state and add one unapproved pilot mission."""

    context = build_unified_dashboard_context(
        DashboardContextStage.CREATIVE_QUALITY
    )
    base_snapshot = context.create_dashboard_service().build_snapshot()
    pilot, result = run_deterministic_real_content_pilot()
    activity = [
        *context.activity_events,
        *[
            ActivityEventSummary(
                event_id=str(event.event_id),
                event_type=ActivityEventType.MISSION,
                title=event.event_type.value.replace("_", " ").title(),
                detail="Safe pilot runtime event; content remains local.",
                occurred_at=event.timestamp,
            )
            for event in pilot.event_bus.filter_by_mission(
                result.mission.mission_id
            )
        ],
    ]
    return DashboardService(
        mode=context.mode,
        data_label=(
            "DETERMINISTIC REAL CONTENT PILOT · FOUNDER REVIEW REQUIRED · "
            "NOT RENDERED · NOT PUBLISHED"
        ),
        employees=base_snapshot.employees,
        missions=[*base_snapshot.missions, result.mission],
        decisions=context.decisions,
        workflows=base_snapshot.workflows,
        system_health=context.system_health,
        activity=activity,
        production_package=context.production_package,
        intelligence_package=context.intelligence_package,
        niche_discovery=context.niche_discovery,
        creative_quality_package=context.creative_quality_package,
        provider_state=context.runtime_snapshot.provider_state,
        real_content_pilot=result.model_dump(mode="json"),
    )
