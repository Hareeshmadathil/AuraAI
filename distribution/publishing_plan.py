"""Disabled, founder-controlled publishing preparation for supported platforms."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from core import AuraBaseModel, utc_now
from distribution.models import DistributionChannel
from mission_control.models import ApprovalRequest, ApprovalState
from production.creator_package import CreatorReadyPackage


class RetryPlan(AuraBaseModel):
    maximum_attempts: int = Field(default=3, ge=1, le=5)
    delays_minutes: list[int] = Field(default=[5, 30, 120])
    automatic_retry: Literal[False] = False


class PublishingSchedule(AuraBaseModel):
    proposed_at: datetime
    timezone: str = "UTC"
    automatic_scheduling: Literal[False] = False


class PlatformPublishingPlan(AuraBaseModel):
    plan_id: UUID
    channel: DistributionChannel
    title: str
    description: str
    hashtags: list[str]
    schedule: PublishingSchedule
    retry: RetryPlan
    policy_checks: list[str]


class UploadManifest(AuraBaseModel):
    manifest_id: UUID
    source_package_id: UUID
    plans: list[PlatformPublishingPlan]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    required_action: str = "approve_publishing_manifest"
    founder_approval_required: Literal[True] = True
    publishing_enabled: Literal[False] = False
    uploaded: Literal[False] = False
    published: Literal[False] = False


class PublishingPreparationService:
    """Prepare immutable plans; this service has no upload capability."""

    CHANNELS = (
        DistributionChannel.YOUTUBE,
        DistributionChannel.INSTAGRAM,
        DistributionChannel.TIKTOK,
    )

    def build(self, package: CreatorReadyPackage) -> UploadManifest:
        plans = [self._plan(package, channel, index) for index, channel in enumerate(self.CHANNELS)]
        payload = [item.model_dump(mode="json") for item in plans]
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return UploadManifest(
            manifest_id=uuid5(NAMESPACE_URL, f"publishing-manifest:{package.package_id}:{digest}"),
            source_package_id=package.package_id,
            plans=plans,
            content_hash=digest,
        )

    @staticmethod
    def validate_approval(manifest: UploadManifest, approval: ApprovalRequest) -> bool:
        """Validate the existing gateway record without enabling publishing."""
        return (
            approval.state == ApprovalState.APPROVED
            and approval.requested_action == manifest.required_action
            and approval.content_hash == manifest.content_hash
            and approval.expires_at > utc_now()
        )

    @staticmethod
    def _plan(package: CreatorReadyPackage, channel: DistributionChannel, index: int) -> PlatformPublishingPlan:
        metadata = package.metadata
        return PlatformPublishingPlan(
            plan_id=uuid5(NAMESPACE_URL, f"publishing-plan:{package.package_id}:{channel.value}"),
            channel=channel,
            title=metadata.title_options[min(index, len(metadata.title_options) - 1)],
            description=metadata.description,
            hashtags=metadata.hashtags,
            schedule=PublishingSchedule(proposed_at=package.final_script.created_at + timedelta(days=index + 1)),
            retry=RetryPlan(),
            policy_checks=[
                "Creative Quality approval is present.",
                "Claims remain supported by cited evidence.",
                "Founder separately approves this exact manifest hash.",
                "Platform policy is reviewed immediately before manual upload.",
            ],
        )
