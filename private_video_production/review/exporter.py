"""Markdown export for private draft review and edit notes."""

from private_video_production.models import PrivateVideoReview


def review_markdown(review: PrivateVideoReview) -> str:
    """Render a safe founder review summary."""

    return (
        "# Private video founder review\n\n"
        f"Decision: {review.decision.value}\n\n"
        f"Placeholders: {review.placeholder_count}\n\n"
        "Publishing approved: false\n\n"
        "PRIVATE DRAFT — FOUNDER REVIEW REQUIRED — NOT PUBLISHED\n"
    )


EDIT_NOTES_TEMPLATE = """# Private draft edit notes

- Synthetic voice naturalness:
- Pronunciation:
- Pacing:
- Hook impact:
- Story clarity:
- Evidence visibility:
- Visual variety:
- Subtitle readability:
- Audio clarity:
- Brand consistency:
- Factual accuracy:
- Privacy:
- Placeholder replacements:
- Overall watchability:
"""
