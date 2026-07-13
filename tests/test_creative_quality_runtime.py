from company_missions import create_review_ready_production_package
from creative_quality.pipeline import create_creative_quality_pipeline
from runtime_engine.models import RuntimeEventType


def test_quality_pipeline_emits_events_and_registers_runtime_state() -> None:
    pipeline = create_creative_quality_pipeline()
    result = pipeline.run(create_review_ready_production_package())
    assert result.success
    snapshot = pipeline.state_manager.snapshot()
    event_types = {event.event_type for event in snapshot.recent_events}
    assert RuntimeEventType.CREATIVE_QUALITY_STARTED in event_types
    assert RuntimeEventType.HOOK_REVIEW_COMPLETED in event_types
    assert RuntimeEventType.CREATIVE_QUALITY_SCORED in event_types
    assert RuntimeEventType.CREATIVE_QUALITY_COMPLETED in event_types
    assert snapshot.creative_quality_packages
    assert snapshot.statistics.creative_quality_packages == 1
