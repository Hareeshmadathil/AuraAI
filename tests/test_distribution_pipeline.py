from distribution.models import DistributionPackage, PublishingState
from distribution.pipeline import create_distribution_pipeline
from runtime_engine.models import RuntimeEventType
from tests.distribution_helpers import production_package, quality_package


def test_quality_package_produces_review_ready_distribution_package() -> None:
    pipeline = create_distribution_pipeline()
    result = pipeline.run(quality_package())

    assert result.success
    package = DistributionPackage.model_validate(
        result.data["distribution_package"]
    )
    assert package.publication_status == PublishingState.READY_FOR_REVIEW
    assert package.predicted_quality_score is not None
    assert package.automatic_publishing is False
    assert result.data["manual_workflow"]["status"] == "completed"
    events = [event.event_type for event in pipeline.event_bus.list_events()]
    assert RuntimeEventType.DISTRIBUTION_STARTED in events
    assert RuntimeEventType.DISTRIBUTION_COMPLETED in events


def test_production_package_remains_not_ready_until_quality_review() -> None:
    result = create_distribution_pipeline().run(production_package())

    assert result.success
    package = DistributionPackage.model_validate(
        result.data["distribution_package"]
    )
    assert package.publication_status == PublishingState.NOT_READY
    assert not package.publish_checklist[0].completed
