"""Founder content-review gate tests."""

import pytest

from company_missions.first_real_content.dashboard import create_sample_first_content_input
from company_missions.first_real_content.review import FirstContentFounderReviewService
from company_missions.first_real_content.runner import FirstRealContentMissionRunner
from core import ValidationError


def test_revision_is_bounded_and_does_not_approve_delivery() -> None:
    runner = FirstRealContentMissionRunner()
    result = runner.run_typed(create_sample_first_content_input())
    service = FirstContentFounderReviewService(runner)
    revised = service.request_content_revision(result, "Tighten the opening.")
    assert revised.production_review.rendered is False
    assert revised.production_review.published is False
    with pytest.raises(ValidationError):
        service.request_content_revision(revised, "Again")


def test_rejection_preserves_packages_and_marks_failed() -> None:
    runner = FirstRealContentMissionRunner()
    result = runner.run_typed(create_sample_first_content_input())
    rejected = FirstContentFounderReviewService(runner).reject_content(result, "Needs evidence.")
    assert rejected.mission.status.value == "failed"
    assert rejected.production_package.package_id == result.production_package.package_id


def test_content_approval_never_approves_render_or_publish() -> None:
    runner = FirstRealContentMissionRunner()
    result = runner.run_typed(create_sample_first_content_input())
    approved = FirstContentFounderReviewService(runner).approve_content(
        result, "Content package approved."
    )
    assert approved.mission.status.value == "completed"
    assert approved.production_review.rendered is False
    assert approved.production_review.published is False


def test_founder_quality_threshold_blocks_approval() -> None:
    runner = FirstRealContentMissionRunner()
    value = create_sample_first_content_input().model_copy(
        update={"founder_quality_threshold": 100}
    )
    result = runner.run_typed(value)
    assert result.production_review.blocking_issues
    with pytest.raises(ValidationError) as caught:
        FirstContentFounderReviewService(runner).approve_content(result, "Approve")
    assert caught.value.error_code == "CONTENT_BLOCKERS_PREVENT_APPROVAL"
