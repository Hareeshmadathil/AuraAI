import pytest
from pydantic import ValidationError

from analytics.models import ManualPerformanceMetrics
from distribution.models import DistributionChannel, PublishingState
from tests.distribution_helpers import distribution_package, manual_metrics


def test_distribution_package_contains_every_required_local_target() -> None:
    package = distribution_package()

    assert package.publication_status == PublishingState.READY_FOR_REVIEW
    assert package.automatic_publishing is False
    assert package.youtube_package.channel == DistributionChannel.YOUTUBE
    assert package.shorts_package.channel == DistributionChannel.YOUTUBE_SHORTS
    assert package.instagram_package.channel == DistributionChannel.INSTAGRAM
    assert package.tiktok_package.channel == DistributionChannel.TIKTOK
    assert package.linkedin_package.channel == DistributionChannel.LINKEDIN
    assert package.twitter_x_package.channel == DistributionChannel.TWITTER_X
    assert package.community_post.channel == DistributionChannel.COMMUNITY
    assert package.upload_instructions
    assert package.chapter_markers


def test_manual_metrics_validate_audience_totals() -> None:
    package = distribution_package()
    values = manual_metrics(package).model_dump()
    values.update({"views": 10, "new_viewers": 8, "returning_viewers": 8})

    with pytest.raises(ValidationError):
        ManualPerformanceMetrics.model_validate(values)
