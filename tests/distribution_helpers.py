"""Shared deterministic fixtures for Distribution and Analytics tests."""

from analytics.models import ManualPerformanceMetrics
from company_missions import create_review_ready_production_package
from creative_quality.models import CreativeQualityPackage
from creative_quality.pipeline import create_creative_quality_pipeline
from distribution.approval import DistributionApprovalService
from distribution.models import (
    DistributionChannel,
    DistributionPackage,
)
from distribution.providers import DeterministicDistributionProvider
from production.models import ProductionPackage


def production_package() -> ProductionPackage:
    return create_review_ready_production_package()


def quality_package() -> CreativeQualityPackage:
    result = create_creative_quality_pipeline().run(production_package())
    assert result.success
    return CreativeQualityPackage.model_validate(
        result.data["creative_quality_package"]
    )


def distribution_package() -> DistributionPackage:
    return DeterministicDistributionProvider().prepare_package(quality_package())


def manually_uploaded_package() -> DistributionPackage:
    package = distribution_package()
    service = DistributionApprovalService()
    keys = {
        item.key
        for item in package.manual_approval_checklist.items
        if item.required
    }
    package = service.approve(
        package,
        founder_name="Test Founder",
        approval_note="Reviewed in a deterministic unit test.",
        confirmed_checklist_keys=keys,
    )
    package = service.mark_ready_to_upload(package)
    return service.confirm_manual_upload(package, founder_confirmed=True)


def manual_metrics(package: DistributionPackage) -> ManualPerformanceMetrics:
    return ManualPerformanceMetrics(
        distribution_package_id=package.package_id,
        platform=DistributionChannel.YOUTUBE,
        views=1000,
        click_through_rate=5,
        average_view_duration_seconds=120,
        retention_percentage=50,
        watch_time_hours=33.3,
        likes=75,
        comments=15,
        shares=10,
        subscribers_gained=20,
        impressions=20_000,
        traffic_sources={"browse": 700, "search": 300},
        countries={"India": 600, "Other": 400},
        devices={"mobile": 800, "desktop": 200},
        returning_viewers=300,
        new_viewers=700,
        upload_hour_utc=14,
    )
