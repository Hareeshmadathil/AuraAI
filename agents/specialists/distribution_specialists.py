"""Founder-controlled distribution specialist employees."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from distribution.models import DistributionPackage


class _DistributionSpecialist(BaseEmployee):
    """Share validated extraction behavior across distribution roles."""

    def __init__(
        self,
        *,
        name: str,
        job_title: str,
        description: str,
        output_key: str,
        extractor: Callable[[DistributionPackage], Any],
    ) -> None:
        super().__init__(
            name=name,
            job_title=job_title,
            department=DepartmentName.DISTRIBUTION,
            description=description,
        )
        self.output_key = output_key
        self._extractor = extractor

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return one typed part from an explicit local package."""

        raw = task.input_data.get("distribution_package")
        if raw is None:
            return OperationResult.failure(
                "distribution_package is required.",
                error_code="MISSING_DISTRIBUTION_PACKAGE",
            )
        try:
            package = DistributionPackage.model_validate(raw)
        except Exception as error:
            return OperationResult.failure(
                "distribution_package is invalid.",
                error_code="INVALID_DISTRIBUTION_PACKAGE",
                data={"exception_type": error.__class__.__name__},
            )
        value = self._extractor(package)
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        return OperationResult.ok(
            f"{self.job_title} prepared local review output.",
            data={self.output_key: value},
        )


class YouTubeDistributionSpecialist(_DistributionSpecialist):
    def __init__(self) -> None:
        super().__init__(
            name="Broadcast",
            job_title="YouTube Distribution Specialist",
            description="Prepares long-form YouTube upload guidance locally.",
            output_key="youtube_package",
            extractor=lambda package: package.youtube_package,
        )


class ShortFormDistributionSpecialist(_DistributionSpecialist):
    def __init__(self) -> None:
        super().__init__(
            name="Vertical",
            job_title="Short-form Distribution Specialist",
            description="Prepares reviewed vertical-video platform packages.",
            output_key="short_form_packages",
            extractor=lambda package: {
                "youtube_shorts": package.shorts_package.model_dump(mode="json"),
                "instagram": package.instagram_package.model_dump(mode="json"),
                "tiktok": package.tiktok_package.model_dump(mode="json"),
            },
        )


class SEOPublisher(_DistributionSpecialist):
    def __init__(self) -> None:
        super().__init__(
            name="Index",
            job_title="SEO Publisher",
            description="Prepares deterministic search metadata without publishing.",
            output_key="seo_metadata",
            extractor=lambda package: {
                "tags": package.tags,
                "hashtags": package.hashtags,
                "playlist_suggestion": package.playlist_suggestion,
                "chapter_markers": [
                    item.model_dump(mode="json")
                    for item in package.chapter_markers
                ],
            },
        )


class MetadataSpecialist(_DistributionSpecialist):
    def __init__(self) -> None:
        super().__init__(
            name="Ledger",
            job_title="Metadata Specialist",
            description="Validates platform metadata and manual upload instructions.",
            output_key="metadata_package",
            extractor=lambda package: package.metadata_package,
        )
