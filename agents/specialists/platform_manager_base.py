"""Shared typed foundation for AuraAI platform managers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from agents.base_employee import BaseEmployee
from agents.specialists.seo_specialist import SEOPlan
from core import (
    AuraBaseModel,
    ContentPlatform,
    DepartmentName,
    OperationResult,
    TaskRecord,
    ValidationError,
)


class PlatformContentFormat(AuraBaseModel):
    """One content format assigned to a supported platform."""

    format_id: UUID = Field(default_factory=uuid4)
    platform: ContentPlatform
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=2000)
    production_guidance: list[str] = Field(min_length=1)


class PlatformGrowthPlan(AuraBaseModel):
    """Deterministic audience and monetization guidance."""

    audience_retention_priorities: list[str] = Field(min_length=1)
    engagement_priorities: list[str] = Field(min_length=1)
    monetization_paths: list[str] = Field(min_length=1)
    guaranteed_earnings: bool = False

    @model_validator(mode="after")
    def reject_guaranteed_earnings(self) -> "PlatformGrowthPlan":
        """Prevent plans from promising financial outcomes."""

        if self.guaranteed_earnings:
            raise ValueError("Platform plans cannot guarantee earnings.")
        return self


class PlatformPublishingPlan(AuraBaseModel):
    """Complete strategy-only publishing plan for platform managers."""

    platform_plan_id: UUID = Field(default_factory=uuid4)
    brand_name: str = Field(min_length=1, max_length=200)
    positioning: str = Field(min_length=1, max_length=2000)
    target_audience: str = Field(min_length=1, max_length=2000)
    content_pillars: list[str] = Field(min_length=1)
    campaign_goal: str = Field(min_length=1, max_length=2000)
    supported_platforms: list[ContentPlatform] = Field(min_length=1)
    platform_roles: dict[ContentPlatform, str] = Field(min_length=1)
    content_formats: list[PlatformContentFormat] = Field(min_length=1)
    publishing_cadence: str = Field(min_length=1, max_length=1000)
    profile_guidance: list[str] = Field(default_factory=list)
    title_guidance: list[str] = Field(default_factory=list)
    thumbnail_guidance: list[str] = Field(default_factory=list)
    caption_guidance: list[str] = Field(default_factory=list)
    hashtag_guidance: list[str] = Field(default_factory=list)
    hook_and_pacing_guidance: list[str] = Field(default_factory=list)
    growth_plan: PlatformGrowthPlan
    seo_plan_id: UUID

    @model_validator(mode="after")
    def validate_platform_scope(self) -> "PlatformPublishingPlan":
        """Ensure formats and roles cannot leak unsupported platforms."""

        supported = set(self.supported_platforms)
        role_platforms = set(self.platform_roles)
        format_platforms = {
            content_format.platform
            for content_format in self.content_formats
        }

        if role_platforms != supported:
            raise ValueError(
                "Platform roles must exactly match supported platforms."
            )
        if not format_platforms.issubset(supported):
            raise ValueError(
                "Content formats contain an unsupported platform."
            )
        return self


class PlatformManagerBase(BaseEmployee, ABC):
    """Shared validation and lifecycle behavior for platform managers."""

    def __init__(self, *, name: str, job_title: str) -> None:
        super().__init__(
            name=name,
            job_title=job_title,
            department=DepartmentName.MARKETING,
            description=(
                "Creates deterministic platform publishing and growth "
                "plans without accessing accounts or external APIs."
            ),
        )

    @property
    @abstractmethod
    def supported_platforms(self) -> frozenset[ContentPlatform]:
        """Return platforms owned by this manager."""

        raise NotImplementedError

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Validate structured input and return a platform plan."""

        input_data = task.input_data
        plan = self.create_platform_plan(
            brand_name=self._require_text(input_data, "brand_name"),
            positioning=self._require_text(input_data, "positioning"),
            target_audience=self._require_text(
                input_data,
                "target_audience",
            ),
            content_pillars=self._require_string_list(
                input_data,
                "content_pillars",
            ),
            campaign_goal=self._require_text(
                input_data,
                "campaign_goal",
            ),
            publishing_frequency=self._require_text(
                input_data,
                "publishing_frequency",
            ),
            seo_plan=self._require_seo_plan(input_data),
        )

        return OperationResult.ok(
            f"{self.job_title} created the platform publishing plan.",
            data={
                "platform_plan": plan.model_dump(mode="json"),
            },
        )

    @abstractmethod
    def create_platform_plan(
        self,
        *,
        brand_name: str,
        positioning: str,
        target_audience: str,
        content_pillars: list[str],
        campaign_goal: str,
        publishing_frequency: str,
        seo_plan: SEOPlan,
    ) -> PlatformPublishingPlan:
        """Create the concrete manager's deterministic platform plan."""

        raise NotImplementedError

    def _validate_seo_platform(self, seo_plan: SEOPlan) -> None:
        """Reject SEO plans belonging to unsupported platforms."""

        if seo_plan.platform not in self.supported_platforms:
            raise ValidationError(
                "SEO plan platform is unsupported by this manager.",
                details={
                    "platform": seo_plan.platform.value,
                    "supported_platforms": sorted(
                        platform.value
                        for platform in self.supported_platforms
                    ),
                },
            )

    @staticmethod
    def _require_text(input_data: dict[str, Any], key: str) -> str:
        """Return one required non-empty string."""

        value = input_data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(
                f"Platform manager requires non-empty '{key}' input.",
                details={"required_key": key},
            )
        return value.strip()

    @staticmethod
    def _require_string_list(
        input_data: dict[str, Any],
        key: str,
    ) -> list[str]:
        """Return one required list of non-empty strings."""

        value = input_data.get(key)
        if (
            not isinstance(value, list)
            or not value
            or any(
                not isinstance(item, str) or not item.strip()
                for item in value
            )
        ):
            raise ValidationError(
                f"Platform manager requires '{key}' as non-empty strings.",
                details={"required_key": key},
            )
        return [item.strip() for item in value]

    def _require_seo_plan(self, input_data: dict[str, Any]) -> SEOPlan:
        """Parse and scope the required SEO plan."""

        value = input_data.get("seo_plan")
        if isinstance(value, SEOPlan):
            seo_plan = value
        elif isinstance(value, dict):
            try:
                seo_plan = SEOPlan.model_validate(value)
            except Exception as error:
                raise ValidationError(
                    "The supplied SEO plan is invalid.",
                    details={
                        "exception_type": error.__class__.__name__,
                    },
                ) from error
        else:
            raise ValidationError(
                "Platform manager requires seo_plan in task.input_data.",
                details={"required_key": "seo_plan"},
            )

        self._validate_seo_platform(seo_plan)
        return seo_plan
