from core import DepartmentName, MissionRecord, MissionStatus
from intelligence.models import IntelligencePackage
from intelligence.pipeline import create_intelligence_pipeline
from runtime_engine.models import RuntimeEventType


def test_pipeline_produces_every_report_and_runtime_projection() -> None:
    pipeline = create_intelligence_pipeline()
    result = pipeline.run("AI productivity for small businesses")
    package = IntelligencePackage.model_validate(
        result.data["intelligence_package"]
    )
    snapshot = pipeline.state_manager.snapshot()

    assert result.success is True
    assert package.trend_report
    assert package.competitor_report
    assert package.audience_persona
    assert package.seo_report
    assert package.thumbnail_analysis
    assert package.hook_analysis
    assert snapshot.statistics.intelligence_packages == 1
    assert snapshot.intelligence_packages[0].package_id == package.package_id
    assert snapshot.workflows[0].progress_percentage == 100
    assert {
        event.event_type for event in snapshot.recent_events
    } >= {
        RuntimeEventType.INTELLIGENCE_STARTED,
        RuntimeEventType.INTELLIGENCE_STAGE_COMPLETED,
        RuntimeEventType.INTELLIGENCE_COMPLETED,
    }


def test_pipeline_accepts_approved_mission() -> None:
    mission = MissionRecord(
        title="Analyze creator workflows",
        description="Create pre-production intelligence.",
        lead_department=DepartmentName.INTELLIGENCE,
        context={"selected_niche": "Creator workflow education"},
    )
    mission.approve("Approved for deterministic analysis.")

    result = create_intelligence_pipeline().run(mission)
    package = IntelligencePackage.model_validate(
        result.data["intelligence_package"]
    )

    assert result.success is True
    assert package.mission_id == mission.mission_id


def test_pipeline_rejects_unapproved_or_terminal_mission() -> None:
    mission = MissionRecord(
        title="Draft intelligence",
        description="Not yet approved.",
        status=MissionStatus.DRAFT,
    )
    result = create_intelligence_pipeline().run(mission)
    assert result.success is False
