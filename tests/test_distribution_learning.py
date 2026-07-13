from analytics.models import AnalyticsReport, LearningReport
from analytics.pipeline import create_analytics_pipelines
from tests.distribution_helpers import manual_metrics, manually_uploaded_package


def test_learning_compares_quality_heuristics_with_real_metrics() -> None:
    package = manually_uploaded_package()
    metrics = manual_metrics(package)
    analytics_pipeline, learning_pipeline = create_analytics_pipelines()
    analytics_result = analytics_pipeline.run(package, metrics)
    report = AnalyticsReport.model_validate(
        analytics_result.data["analytics_report"]
    )

    result = learning_pipeline.run(package, report)

    assert result.success
    learning = LearningReport.model_validate(result.data["learning_report"])
    assert {item.dimension for item in learning.comparisons} == {
        "hook",
        "retention",
        "thumbnail",
        "overall_quality",
    }
    assert learning.improvement_recommendations
    assert not learning.ml_training_performed
    assert not learning.online_learning_performed
