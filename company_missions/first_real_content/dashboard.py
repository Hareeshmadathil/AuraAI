"""Cumulative, deterministic dashboard composition for the first mission."""

from app.dashboard.models import ActivityEventSummary, ActivityEventType
from app.dashboard.service import DashboardService
from company_missions.real_content_pilot.dashboard import (
    create_real_content_pilot_demo_dashboard_service,
)
from core import ContentPlatform, utc_now

from company_missions.first_real_content.models import FirstContentMissionInput
from company_missions.first_real_content.runner import FirstRealContentMissionRunner


def create_sample_first_content_input() -> FirstContentMissionInput:
    return FirstContentMissionInput(
        mission_title="First Founder-Reviewed Content Mission",
        objective="Prepare a complete evidence-aware content package for founder review.",
        topic="Practical AI productivity systems for small businesses",
        target_audience="Owners and operators of small businesses",
        audience_problem="They need practical AI workflows without unsupported promises.",
        audience_promise="A reviewable system for evaluating one practical workflow.",
        content_goal="Teach a safe, repeatable productivity workflow.",
        primary_platform=ContentPlatform.YOUTUBE,
        language="English",
        tone="Clear, practical, and evidence-aware",
        preferred_video_style=None,
        target_duration_seconds=240,
        primary_call_to_action="Document one workflow and review the evidence.",
        source_notes=["Founder-supplied sample direction."],
        constraints=["No fabricated statistics", "No guaranteed outcomes"],
        prohibited_claims=["Guaranteed revenue"],
        preferred_keywords=["AI productivity systems", "small business workflow"],
        sample_data=True,
        requested_at=utc_now(),
    )


def create_first_content_mission_demo_dashboard_service() -> DashboardService:
    """Build cumulative sample state without networking, exporting, or delivery."""

    base = create_real_content_pilot_demo_dashboard_service().build_snapshot()
    runner = FirstRealContentMissionRunner()
    result = runner.run_typed(create_sample_first_content_input())
    activity = [
        *base.activity,
        *[
            ActivityEventSummary(
                event_id=str(event.event_id),
                event_type=ActivityEventType.MISSION,
                title=event.event_type.value.replace("_", " ").title(),
                detail="Safe first-content mission event.",
                occurred_at=event.timestamp,
            )
            for event in runner.event_bus.list_events()
        ],
    ]
    return DashboardService(
        mode=base.mode,
        data_label="SAMPLE FIRST CONTENT MISSION · FOUNDER REVIEW REQUIRED · NOT RENDERED · NOT PUBLISHED",
        employees=base.employees,
        missions=[*base.missions, result.mission],
        decisions=base.recent_decisions,
        workflows=base.workflows,
        system_health=base.system_health,
        activity=activity,
        production_package=result.production_package,
        intelligence_package=base.intelligence,
        niche_discovery=base.niche_discovery,
        creative_quality_package=result.creative_quality_package,
        provider_state=base.providers,
        real_content_pilot=base.real_content_pilot,
        first_content_mission=result.dashboard_projection(),
    )
