"""Typed manually supplied analytics and deterministic learning reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import AuraBaseModel, utc_now
from distribution.models import DistributionChannel


class ManualPerformanceMetrics(AuraBaseModel):
    """Performance data entered or imported explicitly by the founder."""

    distribution_package_id: UUID
    platform: DistributionChannel
    views: int = Field(ge=0)
    click_through_rate: float = Field(ge=0, le=100)
    average_view_duration_seconds: float = Field(ge=0)
    retention_percentage: float = Field(ge=0, le=100)
    watch_time_hours: float = Field(ge=0)
    likes: int = Field(ge=0)
    comments: int = Field(ge=0)
    shares: int = Field(ge=0)
    subscribers_gained: int = Field(ge=0)
    impressions: int = Field(ge=0)
    traffic_sources: dict[str, int] = Field(default_factory=dict)
    countries: dict[str, int] = Field(default_factory=dict)
    devices: dict[str, int] = Field(default_factory=dict)
    returning_viewers: int = Field(ge=0)
    new_viewers: int = Field(ge=0)
    upload_hour_utc: int | None = Field(default=None, ge=0, le=23)
    measured_at: datetime = Field(default_factory=utc_now)
    manually_supplied: Literal[True] = True

    @model_validator(mode="after")
    def validate_audience_counts(self) -> "ManualPerformanceMetrics":
        if self.returning_viewers + self.new_viewers > self.views:
            raise ValueError("New and returning viewers cannot exceed views.")
        return self


class AnalyticsReport(AuraBaseModel):
    """Derived performance ratios from one manual metrics submission."""

    report_id: UUID = Field(default_factory=uuid4)
    metrics: ManualPerformanceMetrics
    engagement_rate: float = Field(ge=0)
    subscriber_conversion_rate: float = Field(ge=0)
    share_rate: float = Field(ge=0)
    returning_viewer_rate: float = Field(ge=0, le=100)
    top_traffic_source: str | None = None
    top_country: str | None = None
    top_device: str | None = None
    observations: list[str] = Field(default_factory=list)
    deterministic: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class MetricComparison(AuraBaseModel):
    """Transparent comparison between a heuristic and observed metric."""

    dimension: str = Field(min_length=1, max_length=100)
    predicted_score: float = Field(ge=0, le=100)
    observed_score: float = Field(ge=0, le=100)
    difference: float = Field(ge=-100, le=100)
    interpretation: str = Field(min_length=1, max_length=1000)


class LearningReport(AuraBaseModel):
    """Deterministic recommendations; no model training is performed."""

    report_id: UUID = Field(default_factory=uuid4)
    distribution_package_id: UUID
    analytics_report_id: UUID
    comparisons: list[MetricComparison] = Field(default_factory=list)
    improvement_recommendations: list[str] = Field(default_factory=list)
    future_hook_suggestions: list[str] = Field(default_factory=list)
    thumbnail_observations: list[str] = Field(default_factory=list)
    retention_observations: list[str] = Field(default_factory=list)
    seo_observations: list[str] = Field(default_factory=list)
    upload_timing_observations: list[str] = Field(default_factory=list)
    deterministic: bool = True
    ml_training_performed: bool = False
    online_learning_performed: bool = False
    created_at: datetime = Field(default_factory=utc_now)
