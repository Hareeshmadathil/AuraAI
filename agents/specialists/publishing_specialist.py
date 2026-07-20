"""Publishing specialist for preparing deterministic publishing manifests."""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from distribution.models import DistributionPackage
from mission_control.models import PublishingManifest
from runtime_engine.artifact_context import ArtifactResolver, IntegrityVerifier


class PublishingSpecialist(BaseEmployee):
    """Employee responsible for generating canonical publishing manifests."""

    def __init__(
        self,
        artifact_resolver: ArtifactResolver,
        integrity_verifier: IntegrityVerifier,
    ) -> None:
        super().__init__(
            name="Publishing Specialist",
            job_title="Publishing Operations Manager",
            department=DepartmentName.DISTRIBUTION,
            description="Prepares deterministic content manifests for final publishing.",
        )
        self.resolver = artifact_resolver
        self.verifier = integrity_verifier

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Verify inputs and generate a deterministic publishing manifest."""

        # Extract required inputs
        media_artifact_id = task.input_data.get("media_artifact_id")
        if not media_artifact_id:
            return OperationResult.failure(
                "Missing media_artifact_id in task payload.",
                error_code="MISSING_MEDIA_ARTIFACT"
            )

        destination = task.input_data.get("destination")
        if not destination:
            return OperationResult.failure(
                "Missing destination in task payload.",
                error_code="MISSING_DESTINATION"
            )

        raw_package = task.input_data.get("distribution_package")
        if not raw_package:
            return OperationResult.failure(
                "Missing distribution_package in task payload.",
                error_code="MISSING_DISTRIBUTION_PACKAGE"
            )

        try:
            package = DistributionPackage.model_validate(raw_package)
        except Exception as error:
            return OperationResult.failure(
                "distribution_package is invalid.",
                error_code="INVALID_DISTRIBUTION_PACKAGE",
                data={"exception_type": error.__class__.__name__, "error_details": str(error)}
            )

        # Verify artifacts
        try:
            from uuid import UUID
            # We don't have the expected hash here unless passed in input_data,
            # but we can resolve to ensure it exists.
            media_record = self.resolver.resolve_artifact(UUID(str(media_artifact_id)))
            if not media_record:
                return OperationResult.failure(
                    f"Media artifact {media_artifact_id} not found.",
                    error_code="INVALID_ARTIFACT"
                )
            
            # Additional artifacts (e.g., thumbnail) could be verified similarly
            thumbnail_artifact_id = task.input_data.get("thumbnail_artifact_id")
            if thumbnail_artifact_id:
                thumb_record = self.resolver.resolve_artifact(UUID(str(thumbnail_artifact_id)))
                if not thumb_record:
                    return OperationResult.failure(
                        f"Thumbnail artifact {thumbnail_artifact_id} not found.",
                        error_code="INVALID_ARTIFACT"
                    )

        except Exception as error:
            return OperationResult.failure(
                f"Artifact verification failed: {str(error)}",
                error_code="ARTIFACT_VERIFICATION_FAILED"
            )

        # Normalize destination
        normalized_dest = str(destination).strip().lower()

        mission_id_str = task.input_data.get("mission_id")
        if not mission_id_str:
            return OperationResult.failure(
                "Missing mission_id in task payload.",
                error_code="MISSING_MISSION_ID"
            )

        # Build Manifest
        try:
            manifest = PublishingManifest(
                mission_id=mission_id_str,
                task_id=task.task_id,
                render_job_id=task.input_data.get("render_job_id"),
                destination=normalized_dest,
                media_artifact_id=media_artifact_id,
                thumbnail_artifact_id=thumbnail_artifact_id,
                source_artifact_ids=[package.package_id],
                title=package.metadata_package.title,
                description=package.metadata_package.description,
                caption=package.metadata_package.description, # fallback to description if not available
                hashtags=package.hashtags,
                tags=package.tags,
                language=package.metadata_package.language,
                content_version=task.input_data.get("content_version", 1),
            )
            
            # Map platform specific caption if available
            if normalized_dest == "youtube":
                manifest.caption = package.youtube_package.caption
            elif normalized_dest == "tiktok":
                manifest.caption = package.tiktok_package.caption
            elif normalized_dest == "instagram":
                manifest.caption = package.instagram_package.caption

        except Exception as error:
            return OperationResult.failure(
                f"Manifest creation failed: {str(error)}",
                error_code="MANIFEST_CREATION_FAILED",
                data={"exception_type": error.__class__.__name__}
            )

        return OperationResult.ok(
            "Publishing manifest successfully generated.",
            data={"manifest": manifest.model_dump(mode="json", exclude_none=True)}
        )
