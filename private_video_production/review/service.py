"""Founder-only review decisions for a verified private draft."""

from __future__ import annotations

from core import ValidationError, utc_now

from private_video_production.models import (
    PrivateVideoReview,
    RenderResult,
    ReviewDecision,
)


class PrivateVideoReviewService:
    """Record approve-private, edit, or reject decisions without publishing."""

    def decide(
        self,
        review: PrivateVideoReview,
        render_result: RenderResult,
        decision: ReviewDecision,
        *,
        founder_confirmed: bool,
        notes: str = "",
    ) -> PrivateVideoReview:
        if not founder_confirmed:
            raise ValidationError("Explicit founder confirmation is required.")
        if not render_result.verified:
            raise ValidationError("Only a verified private draft can be reviewed.")
        if decision == ReviewDecision.PENDING:
            raise ValidationError("A concrete private review decision is required.")
        return review.model_copy(
            update={
                "decision": decision,
                "notes": notes,
                "reviewed_at": utc_now(),
                "publishing_approved": False,
            }
        )
