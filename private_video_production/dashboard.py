"""Cumulative deterministic dashboard projection without media generation."""

from __future__ import annotations

from pathlib import Path

from app.dashboard.service import DashboardService
from company_missions.first_real_content.dashboard import (
    create_first_content_mission_demo_dashboard_service,
)

from private_video_production.loader import MissionZeroPackageLoader
from private_video_production.scenes import MissionZeroScenePlanner


def create_private_video_production_demo_dashboard_service() -> DashboardService:
    """Build a planning-only page with no voice synthesis or rendering."""

    repository_root = Path(__file__).resolve().parents[1]
    package_root = (
        repository_root
        / "outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a"
    )
    production_input = MissionZeroPackageLoader().load(
        package_root,
        repository_root / "outputs/private-video/dashboard-demo",
    )
    scenes, requirements = MissionZeroScenePlanner().plan(production_input)
    base = create_first_content_mission_demo_dashboard_service().build_snapshot()
    projection = {
        "mission_id": str(production_input.mission_id),
        "mission_name": "AuraAI Mission Zero — Building an AI Company in Public",
        "script_version": production_input.script_version,
        "content_approval": "pending",
        "private_render_approval": "pending",
        "publishing_approval": "not_available",
        "selected_voice": None,
        "audition_status": "not_created",
        "narration_status": "not_created",
        "scene_count": len(scenes),
        "required_founder_assets": len(requirements),
        "supplied_assets": 0,
        "placeholder_count": sum(scene.founder_capture_required for scene in scenes),
        "timeline_duration_seconds": production_input.estimated_duration_seconds,
        "subtitle_max_characters": 42,
        "subtitle_max_lines": 2,
        "subtitle_max_cps": 20,
        "render_readiness": "blocked_pending_approvals_voice_and_assets",
        "render_status": "not_rendered",
        "output_resolution": "1920×1080 planned",
        "output_duration": None,
        "verification_status": "not_started",
        "private_review_status": "pending",
        "published": False,
        "demo_only": True,
    }
    return DashboardService(
        mode=base.mode,
        data_label="PRIVATE VIDEO PLANNING DEMO · NO VOICE GENERATED · NOT RENDERED · NOT PUBLISHED",
        employees=base.employees,
        missions=base.missions,
        decisions=base.recent_decisions,
        workflows=base.workflows,
        system_health=base.system_health,
        activity=base.activity,
        production_package=base.production,
        intelligence_package=base.intelligence,
        niche_discovery=base.niche_discovery,
        creative_quality_package=base.creative_quality,
        distribution_package=base.distribution,
        analytics_report=base.analytics,
        learning_report=base.learning,
        provider_state=base.providers,
        real_content_pilot=base.real_content_pilot,
        first_content_mission=base.first_content_mission,
        private_video_production=projection,
    )
