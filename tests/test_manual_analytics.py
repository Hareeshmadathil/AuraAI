from analytics.models import AnalyticsReport
from analytics.pipeline import create_analytics_pipelines
from distribution.models import DistributionPackage, PublishingState
from tests.distribution_helpers import manual_metrics, manually_uploaded_package


def test_analytics_pipeline_imports_only_manual_metrics() -> None:
    package = manually_uploaded_package()
    metrics = manual_metrics(package)
    pipeline, _ = create_analytics_pipelines()

    result = pipeline.run(package, metrics)

    assert result.success
    report = AnalyticsReport.model_validate(result.data["analytics_report"])
    updated = DistributionPackage.model_validate(
        result.data["distribution_package"]
    )
    assert report.metrics.manually_supplied
    assert report.engagement_rate == 10
    assert report.top_traffic_source == "browse"
    assert updated.publication_status == PublishingState.METRICS_IMPORTED


def test_analytics_rejects_metrics_before_manual_upload() -> None:
    package = manually_uploaded_package().model_copy(
        update={"publication_status": PublishingState.READY_TO_UPLOAD}
    )
    pipeline, _ = create_analytics_pipelines()

    result = pipeline.run(package, manual_metrics(package))

    assert not result.success
    assert result.error_code == "MANUAL_UPLOAD_REQUIRED"
