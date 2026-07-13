from analytics.models import AnalyticsReport, LearningReport
from analytics.pipeline import create_analytics_pipelines
from distribution.pipeline import create_distribution_pipeline
from runtime_engine.models import RuntimeEventType
from tests.distribution_helpers import manual_metrics, manually_uploaded_package


def test_runtime_registers_distribution_analytics_and_learning() -> None:
    package = manually_uploaded_package()
    distribution_pipeline = create_distribution_pipeline()
    state = distribution_pipeline.state_manager
    state.register_distribution_package(package)
    analytics_pipeline, learning_pipeline = create_analytics_pipelines(
        state_manager=state,
        event_bus=state.event_bus,
    )
    analytics_result = analytics_pipeline.run(package, manual_metrics(package))
    report = AnalyticsReport.model_validate(
        analytics_result.data["analytics_report"]
    )
    learning_result = learning_pipeline.run(package, report)
    learning = LearningReport.model_validate(
        learning_result.data["learning_report"]
    )

    snapshot = state.snapshot()
    assert snapshot.statistics.distribution_packages == 1
    assert snapshot.statistics.analytics_reports == 1
    assert snapshot.statistics.learning_reports == 1
    assert snapshot.learning_reports[0].report_id == learning.report_id
    events = {event.event_type for event in state.event_bus.list_events()}
    assert RuntimeEventType.METRICS_IMPORTED in events
    assert RuntimeEventType.LEARNING_COMPLETED in events
    assert RuntimeEventType.APPROVAL_CHANGED in events
