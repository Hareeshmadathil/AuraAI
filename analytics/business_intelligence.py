"""Canonical business metrics and deterministic mission-learning handoff."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from analytics.mission_learning import LessonCategory, LessonImpact, MissionLesson
from core import AuraBaseModel
from distribution.models import DistributionChannel
from knowledge_manager.enums import ApprovalStatus


class BusinessMetricSnapshot(AuraBaseModel):
    snapshot_id: UUID
    mission_id: UUID
    platform: DistributionChannel
    impressions: int = Field(ge=0)
    click_through_rate: float = Field(ge=0, le=100)
    watch_time_hours: float = Field(ge=0)
    average_view_duration_seconds: float = Field(ge=0)
    retention_percentage: float = Field(ge=0, le=100)
    subscribers: int = Field(ge=0)
    followers: int = Field(ge=0)
    engagement: int = Field(ge=0)
    revenue: float = Field(ge=0)
    rpm: float = Field(ge=0)
    cpm: float = Field(ge=0)
    affiliate_revenue: float = Field(ge=0)
    sponsorship_revenue: float = Field(ge=0)
    measured_at: datetime
    provenance: dict[str, str]
    verified: bool
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class BusinessMetricsAdapter(Protocol):
    def collect(self, mission_id: UUID) -> BusinessMetricSnapshot: ...


class DeterministicBusinessMetricsAdapter:
    """Replaceable fixture adapter; it performs no platform operation."""

    def collect(self, mission_id: UUID) -> BusinessMetricSnapshot:
        measured = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
        values = {
            "mission_id": str(mission_id), "platform": "youtube", "impressions": 10000,
            "click_through_rate": 5.4, "watch_time_hours": 420.0,
            "average_view_duration_seconds": 252.0, "retention_percentage": 48.0,
            "subscribers": 120, "followers": 120, "engagement": 860,
            "revenue": 175.0, "rpm": 7.5, "cpm": 11.2,
            "affiliate_revenue": 35.0, "sponsorship_revenue": 0.0,
            "measured_at": measured.isoformat(),
        }
        digest = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return BusinessMetricSnapshot(
            snapshot_id=uuid5(NAMESPACE_URL, f"business-metrics:{digest}"),
            mission_id=mission_id, platform=DistributionChannel.YOUTUBE,
            impressions=10000, click_through_rate=5.4, watch_time_hours=420,
            average_view_duration_seconds=252, retention_percentage=48,
            subscribers=120, followers=120, engagement=860, revenue=175,
            rpm=7.5, cpm=11.2, affiliate_revenue=35, sponsorship_revenue=0,
            measured_at=measured, provenance={"adapter": "deterministic", "mode": "offline"},
            verified=True, content_hash=digest,
        )


class BusinessIntelligenceService:
    def lesson(self, metrics: BusinessMetricSnapshot) -> MissionLesson:
        positive = metrics.revenue > 0 and metrics.retention_percentage >= 40
        observation = (
            f"Verified business outcome: revenue {metrics.revenue:.2f}, RPM {metrics.rpm:.2f}, "
            f"CTR {metrics.click_through_rate:.2f}%, retention {metrics.retention_percentage:.2f}%."
        )
        lesson_id = uuid5(NAMESPACE_URL, f"business-lesson:{metrics.content_hash}")
        return MissionLesson(
            lesson_id=lesson_id, source_mission_id=metrics.mission_id,
            category=LessonCategory.REVENUE_RELEVANCE, observation=observation,
            supporting_evidence=[metrics.content_hash], confidence=0.9 if metrics.verified else 0.5,
            impact=LessonImpact.POSITIVE if positive else LessonImpact.IMPROVEMENT,
            affected_subsystem="mission_generator",
            recommended_future_behavior=("Favor mission patterns with verified retention and revenue outcomes."
                                         if positive else "Reduce confidence until retention and revenue improve."),
            success_metric="Improve verified revenue, RPM, CTR, and retention together.",
            freshness_window_days=90, expires_at=metrics.measured_at + timedelta(days=90),
            provenance={"source_mission_id": str(metrics.mission_id),
                        "business_metrics_id": str(metrics.snapshot_id),
                        "business_metrics_hash": metrics.content_hash,
                        **metrics.provenance},
            content_hash=hashlib.sha256(observation.encode()).hexdigest(),
            approval_status=ApprovalStatus.APPROVED if metrics.verified else ApprovalStatus.PENDING,
        )
