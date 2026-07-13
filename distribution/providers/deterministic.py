"""Deterministic offline distribution package preparation."""

from __future__ import annotations

import re
from uuid import UUID

from creative_quality.models import CreativeQualityPackage, QualityGateStatus
from distribution.models import (
    ChapterMarker,
    DistributionChannel,
    DistributionPackage,
    ManualApprovalChecklist,
    MetadataPackage,
    PlatformDistributionPackage,
    PublishChecklistItem,
    PublishingState,
    ThumbnailDistributionPackage,
    UploadInstruction,
)
from production.models import ProductionPackage


class DeterministicDistributionProvider:
    """Prepare stable platform copy using supplied structured content only."""

    def prepare_package(
        self,
        source: CreativeQualityPackage | ProductionPackage,
    ) -> DistributionPackage:
        """Create a package that cannot perform external side effects."""

        if isinstance(source, ProductionPackage):
            return self._from_production(source)
        return self._from_quality(source)

    def _from_production(self, source: ProductionPackage) -> DistributionPackage:
        script = source.script
        tags = self._tags(script.primary_keyword, script.secondary_keywords)
        hashtags = [f"#{self._slug(tag)}" for tag in tags[:8]]
        chapters = self._chapters(source)
        thumbnail = next(
            concept
            for concept in source.thumbnail_plan.concepts
            if concept.concept_id == source.thumbnail_plan.recommended_concept_id
        )
        checklist = self._checklist(quality_complete=False)
        return self._package(
            source_package_id=source.package_id,
            source_kind="production_package",
            title=script.title,
            description=(
                f"{source.input.audience_promise}\n\n"
                f"Manual review required. {script.call_to_action}"
            ),
            hook=script.hook,
            tags=tags,
            hashtags=hashtags,
            chapters=chapters,
            thumbnail=ThumbnailDistributionPackage(
                concept_reference=thumbnail.concept_id,
                headline=thumbnail.primary_text,
                alt_text=thumbnail.visual_composition,
                safety_notes=[
                    "Confirm the final image matches the supplied content.",
                    "Do not imply guaranteed outcomes.",
                ],
            ),
            checklist=checklist,
            state=PublishingState.NOT_READY,
        )

    def _from_quality(
        self,
        source: CreativeQualityPackage,
    ) -> DistributionPackage:
        if source.gate.status == QualityGateStatus.BLOCKED:
            raise ValueError("Blocked Creative Quality packages cannot distribute.")
        if source.gate.status == QualityGateStatus.REVISION_REQUIRED:
            raise ValueError("Creative Quality revisions must be reviewed first.")
        if source.gate.status == QualityGateStatus.FOUNDER_OVERRIDE_REQUIRED:
            raise ValueError("Founder quality review is required first.")
        hook = source.hook_analysis.improved_hook
        title = hook[:120].rstrip(" .") or "Founder-reviewed AuraAI content"
        tags = self._tags("practical guide", ["responsible implementation"])
        hashtags = [f"#{self._slug(tag)}" for tag in tags]
        thumbnail_score = next(
            item
            for item in source.thumbnail_report.concepts
            if item.concept_id == source.thumbnail_report.recommended_concept_id
        )
        return self._package(
            source_package_id=source.package_id,
            source_kind="creative_quality_package",
            title=title,
            description=(
                "Founder-reviewed educational content. Verify all claims and "
                "links before manual upload."
            ),
            hook=hook,
            tags=tags,
            hashtags=hashtags,
            chapters=[
                ChapterMarker(timestamp_seconds=0, title="Opening"),
                ChapterMarker(
                    timestamp_seconds=source.retention_report.call_to_action_timing,
                    title="Next step",
                ),
            ],
            thumbnail=ThumbnailDistributionPackage(
                concept_reference=thumbnail_score.concept_id,
                headline="Clear, truthful takeaway",
                alt_text="Reviewed thumbnail concept for educational content.",
                safety_notes=[source.thumbnail_report.recommendation_reason],
            ),
            checklist=self._checklist(quality_complete=True),
            state=PublishingState.READY_FOR_REVIEW,
            predictions={
                "predicted_quality_score": source.scores.overall,
                "predicted_hook_score": (
                    source.scores.hook
                ),
                "predicted_retention_score": source.scores.retention,
                "predicted_thumbnail_score": source.scores.thumbnail,
            },
        )

    def _package(
        self,
        *,
        source_package_id: UUID,
        source_kind: str,
        title: str,
        description: str,
        hook: str,
        tags: list[str],
        hashtags: list[str],
        chapters: list[ChapterMarker],
        thumbnail: ThumbnailDistributionPackage,
        checklist: list[PublishChecklistItem],
        state: PublishingState,
        predictions: dict[str, float] | None = None,
    ) -> DistributionPackage:
        metadata = MetadataPackage(
            title=title,
            description=description,
            tags=tags,
            hashtags=hashtags,
            playlist_suggestion="AuraAI Practical Guides",
            chapter_markers=chapters,
            seo_notes=[
                "Keep the primary phrase natural in the title and opening.",
                "Validate search assumptions manually before upload.",
            ],
        )
        platforms = {
            channel: self._platform(channel, title, hook, tags, hashtags)
            for channel in DistributionChannel
        }
        instructions = [
            UploadInstruction(
                sequence=index,
                channel=channel,
                instruction=(
                    "Founder manually copies reviewed metadata and selects the "
                    "matching local media file; AuraAI performs no upload."
                ),
            )
            for index, channel in enumerate(DistributionChannel, start=1)
        ]
        approval = ManualApprovalChecklist(
            items=[item.model_copy(deep=True) for item in checklist]
        )
        return DistributionPackage(
            source_package_id=source_package_id,
            source_kind=source_kind,
            publish_checklist=checklist,
            metadata_package=metadata,
            youtube_package=platforms[DistributionChannel.YOUTUBE],
            shorts_package=platforms[DistributionChannel.YOUTUBE_SHORTS],
            instagram_package=platforms[DistributionChannel.INSTAGRAM],
            tiktok_package=platforms[DistributionChannel.TIKTOK],
            linkedin_package=platforms[DistributionChannel.LINKEDIN],
            twitter_x_package=platforms[DistributionChannel.TWITTER_X],
            community_post=platforms[DistributionChannel.COMMUNITY],
            thumbnail_package=thumbnail,
            hashtags=hashtags,
            tags=tags,
            playlist_suggestion=metadata.playlist_suggestion,
            chapter_markers=chapters,
            upload_instructions=instructions,
            manual_approval_checklist=approval,
            publication_status=state,
            **(predictions or {}),
        )

    @staticmethod
    def _platform(
        channel: DistributionChannel,
        title: str,
        hook: str,
        tags: list[str],
        hashtags: list[str],
    ) -> PlatformDistributionPackage:
        roles = {
            DistributionChannel.YOUTUBE: "Long-form educational destination",
            DistributionChannel.YOUTUBE_SHORTS: "Short discovery bridge",
            DistributionChannel.INSTAGRAM: "Reels-first visual summary",
            DistributionChannel.TIKTOK: "Vertical discovery explanation",
            DistributionChannel.LINKEDIN: "Professional learning summary",
            DistributionChannel.TWITTER_X: "Concise discussion prompt",
            DistributionChannel.COMMUNITY: "Audience conversation starter",
        }
        return PlatformDistributionPackage(
            channel=channel,
            title=title,
            caption=f"{hook}\n\nReview the complete guide before acting.",
            content_role=roles[channel],
            tags=tags,
            hashtags=hashtags,
            upload_notes=[
                "Review platform policy and formatting manually.",
                "Confirm media, captions, links, and disclosures before upload.",
            ],
            monetization_note=(
                "Platform monetization may be explored only after eligibility; "
                "no reach or earnings are guaranteed."
            ),
        )

    @staticmethod
    def _checklist(*, quality_complete: bool) -> list[PublishChecklistItem]:
        return [
            PublishChecklistItem(
                key="creative_quality",
                label="Creative Quality gate passed",
                completed=quality_complete,
                guidance="Complete quality review before founder approval.",
            ),
            PublishChecklistItem(
                key="claims",
                label="Claims and sources manually verified",
                guidance="Founder verifies factual claims and disclosures.",
            ),
            PublishChecklistItem(
                key="rights",
                label="Media rights manually confirmed",
                guidance="Founder confirms ownership or licensing for every asset.",
            ),
            PublishChecklistItem(
                key="platform_policy",
                label="Current platform policies reviewed",
                guidance="Founder checks the current platform rules before upload.",
            ),
        ]

    @staticmethod
    def _chapters(source: ProductionPackage) -> list[ChapterMarker]:
        elapsed = 0.0
        chapters: list[ChapterMarker] = []
        for section in source.script.sections:
            chapters.append(
                ChapterMarker(timestamp_seconds=elapsed, title=section.title)
            )
            elapsed += section.estimated_duration_seconds
        return chapters

    @classmethod
    def _tags(cls, primary: str, secondary: list[str]) -> list[str]:
        values = [primary, *secondary, "educational content", "practical guide"]
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))[:15]

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())[:40] or "auraai"
