"""Typed AuraAI brand-review model tests."""

from app.dashboard.brand_models import (
    BrandAssetStatus,
    create_brand_review,
    status_label,
)


def test_brand_review_contains_three_unapproved_concepts() -> None:
    """Keep every concept pending explicit founder selection."""

    review = create_brand_review()

    assert review.brand_name == "AuraAI"
    assert len(review.logo_concepts) == 3
    assert {concept.concept_id for concept in review.logo_concepts} == {
        "a",
        "b",
        "c",
    }
    assert all(
        concept.status == BrandAssetStatus.CONCEPT
        and concept.review_required
        for concept in review.logo_concepts
    )


def test_status_copy_maps_internal_values_without_changing_enums() -> None:
    """Expose clear founder-facing status language."""

    assert status_label("pending_approval") == "Founder Approval Required"
    assert status_label("revision_required") == "Revision Required"
    assert status_label("rendered") == "Rendered Locally"
    assert status_label("custom_state") == "Custom State"
