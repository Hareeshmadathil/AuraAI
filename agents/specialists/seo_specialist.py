"""Deterministic SEO Specialist for AuraAI Creator OS."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from agents.base_employee import BaseEmployee
from core import (
    AuraBaseModel,
    ContentPlatform,
    DepartmentName,
    OperationResult,
    TaskRecord,
    ValidationError,
)


class SEOKeywordCandidate(AuraBaseModel):
    """One keyword candidate with deterministic scoring inputs."""

    candidate_id: UUID = Field(default_factory=uuid4)
    keyword: str = Field(min_length=1, max_length=250)
    relevance_score: float = Field(ge=0.0, le=100.0)
    search_intent_score: float = Field(ge=0.0, le=100.0)
    competition_score: float = Field(ge=0.0, le=100.0)
    monetization_score: float = Field(ge=0.0, le=100.0)
    platform_fit_score: float = Field(ge=0.0, le=100.0)


class SEORecommendation(AuraBaseModel):
    """A ranked keyword recommendation with transparent scoring."""

    candidate_id: UUID
    keyword: str
    seo_score: float = Field(ge=0.0, le=100.0)
    rank: int = Field(ge=1)
    score_breakdown: dict[str, float]


class SEOPlan(AuraBaseModel):
    """Complete deterministic SEO plan for one topic and platform."""

    seo_plan_id: UUID = Field(default_factory=uuid4)
    topic: str = Field(min_length=1, max_length=500)
    target_audience: str = Field(min_length=1, max_length=1000)
    platform: ContentPlatform
    ranked_keywords: list[SEORecommendation] = Field(min_length=1)
    recommended_primary_keyword: str = Field(min_length=1, max_length=250)
    secondary_keywords: list[str]
    title_guidance: str = Field(min_length=1, max_length=2000)
    description_guidance: str = Field(min_length=1, max_length=3000)
    hashtag_guidance: list[str] = Field(min_length=1)
    platform_specific_notes: list[str] = Field(min_length=1)


class SEOSpecialist(BaseEmployee):
    """Marketing specialist that ranks supplied SEO keywords."""

    RELEVANCE_WEIGHT = 0.30
    SEARCH_INTENT_WEIGHT = 0.20
    COMPETITION_WEIGHT = 0.20
    MONETIZATION_WEIGHT = 0.15
    PLATFORM_FIT_WEIGHT = 0.15

    def __init__(self) -> None:
        super().__init__(
            name="Index",
            job_title="SEO Specialist",
            department=DepartmentName.MARKETING,
            description=(
                "Ranks structured keyword candidates and creates "
                "deterministic platform-specific SEO guidance."
            ),
        )

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Create an SEO plan from structured task input."""

        topic = self._require_text(task.input_data, "topic")
        target_audience = self._require_text(
            task.input_data,
            "target_audience",
        )
        platform = self._parse_platform(
            task.input_data.get("platform")
        )
        candidates = self._parse_candidates(
            task.input_data.get("keyword_candidates")
        )
        plan = self.create_seo_plan(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            keyword_candidates=candidates,
        )

        return OperationResult.ok(
            "SEO Specialist created the keyword recommendation plan.",
            data={"seo_plan": plan.model_dump(mode="json")},
        )

    def create_seo_plan(
        self,
        *,
        topic: str,
        target_audience: str,
        platform: ContentPlatform,
        keyword_candidates: list[SEOKeywordCandidate],
    ) -> SEOPlan:
        """Rank candidates and build platform-specific SEO guidance."""

        clean_topic = topic.strip()
        clean_audience = target_audience.strip()

        if not clean_topic or not clean_audience:
            raise ValidationError(
                "SEO topic and target audience cannot be empty."
            )

        recommendations = self.rank_keywords(keyword_candidates)
        primary_keyword = recommendations[0].keyword
        secondary_keywords = [
            recommendation.keyword
            for recommendation in recommendations[1:4]
        ]
        notes = self._platform_notes(platform)

        return SEOPlan(
            topic=clean_topic,
            target_audience=clean_audience,
            platform=platform,
            ranked_keywords=recommendations,
            recommended_primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            title_guidance=(
                f"Use '{primary_keyword}' naturally near the beginning "
                f"of a clear title about {clean_topic}; prioritize "
                "audience value over repetition."
            ),
            description_guidance=(
                f"Explain the value for {clean_audience}, include "
                f"'{primary_keyword}' once in natural context, then add "
                "relevant secondary keywords only where they improve "
                "clarity. Do not make unsupported claims."
            ),
            hashtag_guidance=self._build_hashtags(
                primary_keyword,
                secondary_keywords,
            ),
            platform_specific_notes=notes,
        )

    def rank_keywords(
        self,
        candidates: list[SEOKeywordCandidate],
    ) -> list[SEORecommendation]:
        """Score keywords, rewarding lower competition."""

        if not candidates:
            raise ValidationError(
                "At least one SEO keyword candidate is required."
            )

        scored: list[
            tuple[SEOKeywordCandidate, float, dict[str, float]]
        ] = []

        for candidate in candidates:
            breakdown = {
                "relevance": round(
                    candidate.relevance_score * self.RELEVANCE_WEIGHT,
                    2,
                ),
                "search_intent": round(
                    candidate.search_intent_score
                    * self.SEARCH_INTENT_WEIGHT,
                    2,
                ),
                "competition_advantage": round(
                    (100.0 - candidate.competition_score)
                    * self.COMPETITION_WEIGHT,
                    2,
                ),
                "monetization": round(
                    candidate.monetization_score
                    * self.MONETIZATION_WEIGHT,
                    2,
                ),
                "platform_fit": round(
                    candidate.platform_fit_score
                    * self.PLATFORM_FIT_WEIGHT,
                    2,
                ),
            }
            scored.append(
                (candidate, round(sum(breakdown.values()), 2), breakdown)
            )

        scored.sort(
            key=lambda item: (-item[1], item[0].keyword.casefold())
        )

        return [
            SEORecommendation(
                candidate_id=candidate.candidate_id,
                keyword=candidate.keyword,
                seo_score=score,
                rank=rank,
                score_breakdown=breakdown,
            )
            for rank, (candidate, score, breakdown) in enumerate(
                scored,
                start=1,
            )
        ]

    @staticmethod
    def _require_text(input_data: dict[str, Any], key: str) -> str:
        """Extract one required non-empty string from task input."""

        value = input_data.get(key)

        if not isinstance(value, str) or not value.strip():
            raise ValidationError(
                f"SEO Specialist requires non-empty '{key}' input.",
                details={"required_key": key},
            )

        return value.strip()

    @staticmethod
    def _parse_platform(value: Any) -> ContentPlatform:
        """Validate a supported ContentPlatform input."""

        if isinstance(value, ContentPlatform):
            return value

        try:
            return ContentPlatform(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(
                "SEO platform must be a supported ContentPlatform.",
                details={"received_value": str(value)},
            ) from error

    @staticmethod
    def _parse_candidates(value: Any) -> list[SEOKeywordCandidate]:
        """Validate keyword candidates from task input."""

        if not isinstance(value, list) or not value:
            raise ValidationError(
                "SEO Specialist requires keyword_candidates as a "
                "non-empty list.",
                details={"required_key": "keyword_candidates"},
            )

        candidates: list[SEOKeywordCandidate] = []

        for index, candidate_value in enumerate(value):
            if isinstance(candidate_value, SEOKeywordCandidate):
                candidates.append(candidate_value)
                continue

            if isinstance(candidate_value, dict):
                try:
                    candidates.append(
                        SEOKeywordCandidate.model_validate(candidate_value)
                    )
                    continue
                except Exception as error:
                    raise ValidationError(
                        "An SEO keyword candidate is invalid.",
                        details={
                            "candidate_index": index,
                            "exception_type": error.__class__.__name__,
                        },
                    ) from error

            raise ValidationError(
                "Each SEO keyword candidate must be a model or dictionary.",
                details={
                    "candidate_index": index,
                    "received_type": candidate_value.__class__.__name__,
                },
            )

        return candidates

    @staticmethod
    def _build_hashtags(
        primary_keyword: str,
        secondary_keywords: list[str],
    ) -> list[str]:
        """Create deterministic hashtag suggestions from keywords."""

        keywords = [primary_keyword, *secondary_keywords]
        return [
            "#" + "".join(character for character in keyword.title()
                         if character.isalnum())
            for keyword in keywords
        ]

    @staticmethod
    def _platform_notes(platform: ContentPlatform) -> list[str]:
        """Return deterministic guidance for one supported platform."""

        notes = {
            ContentPlatform.YOUTUBE: [
                "Align title, description, and spoken topic intent.",
                "Use chapters when they improve long-form navigation.",
            ],
            ContentPlatform.YOUTUBE_SHORTS: [
                "Put the search intent in the opening spoken hook.",
                "Keep metadata concise and consistent with the clip.",
            ],
            ContentPlatform.INSTAGRAM: [
                "Use keyword language in the caption and on-screen text.",
                "Prefer a small set of directly relevant hashtags.",
            ],
            ContentPlatform.TIKTOK: [
                "State the topic naturally in the opening narration.",
                "Match caption keywords to the video's actual content.",
            ],
        }
        return notes[platform]
