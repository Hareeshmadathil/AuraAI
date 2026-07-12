"""Tests for AuraAI's deterministic platform managers."""

import pytest

from agents.specialists import (
    InstagramManager,
    SEOKeywordCandidate,
    SEOSpecialist,
    TikTokManager,
    YouTubeManager,
)
from core import (
    ContentPlatform,
    DepartmentName,
    JobStatus,
    TaskRecord,
    ValidationError,
)


def build_seo_plan(platform: ContentPlatform):
    """Create a deterministic SEO plan for one platform."""

    return SEOSpecialist().create_seo_plan(
        topic="Practical AI workflows",
        target_audience="Small business owners",
        platform=platform,
        keyword_candidates=[
            SEOKeywordCandidate(
                keyword="AI workflows for small business",
                relevance_score=95,
                search_intent_score=90,
                competition_score=35,
                monetization_score=80,
                platform_fit_score=90,
            ),
            SEOKeywordCandidate(
                keyword="practical AI automation",
                relevance_score=88,
                search_intent_score=82,
                competition_score=45,
                monetization_score=78,
                platform_fit_score=85,
            ),
        ],
    )


def build_input(platform: ContentPlatform) -> dict[str, object]:
    """Create complete manager input for one SEO platform."""

    return {
        "brand_name": "AuraAI Business Lab",
        "positioning": "Practical, evidence-based AI education.",
        "target_audience": "Small business owners",
        "content_pillars": [
            "AI workflows",
            "Productivity systems",
        ],
        "campaign_goal": "Build qualified audience awareness.",
        "publishing_frequency": "Three useful releases per week.",
        "seo_plan": build_seo_plan(platform),
    }


def execute_manager(manager, platform: ContentPlatform):
    """Execute a manager task and return the structured plan data."""

    task = TaskRecord(
        title=f"Create {platform.value} publishing plan",
        department=DepartmentName.MARKETING,
        input_data=build_input(platform),
    )
    manager.accept_task(task)
    result = manager.execute_current_task()
    assert result.success is True
    assert task.status == JobStatus.COMPLETED
    manager.clear_current_task()
    return result.data["platform_plan"]


def test_youtube_plan_creation_and_shorts_inclusion() -> None:
    """Create linked long-form and Shorts roles and formats."""

    plan = execute_manager(YouTubeManager(), ContentPlatform.YOUTUBE)

    assert set(plan["supported_platforms"]) == {
        "youtube",
        "youtube_shorts",
    }
    assert {item["platform"] for item in plan["content_formats"]} == {
        "youtube",
        "youtube_shorts",
    }
    assert plan["title_guidance"]
    assert plan["thumbnail_guidance"]


def test_instagram_plan_is_reels_first() -> None:
    """Make Reels primary with carousel and Story support."""

    plan = execute_manager(
        InstagramManager(),
        ContentPlatform.INSTAGRAM,
    )

    names = [item["name"] for item in plan["content_formats"]]
    assert names == ["Reel", "Carousel", "Story"]
    assert "Reels-first" in plan["platform_roles"]["instagram"]
    assert plan["profile_guidance"]
    assert plan["caption_guidance"]
    assert plan["hashtag_guidance"]


def test_tiktok_plan_is_vertical_and_distinguishes_formats() -> None:
    """Separate discovery videos from eligibility-aware videos."""

    plan = execute_manager(TikTokManager(), ContentPlatform.TIKTOK)
    names = {item["name"] for item in plan["content_formats"]}

    assert names == {
        "Short discovery video",
        "Extended eligibility-aware video",
    }
    assert plan["hook_and_pacing_guidance"]


@pytest.mark.parametrize(
    ("manager", "platform"),
    [
        (YouTubeManager(), ContentPlatform.YOUTUBE_SHORTS),
        (InstagramManager(), ContentPlatform.INSTAGRAM),
        (TikTokManager(), ContentPlatform.TIKTOK),
    ],
)
def test_each_manager_preserves_employee_lifecycle(
    manager,
    platform: ContentPlatform,
) -> None:
    """Run every manager through BaseEmployee task handling."""

    plan = execute_manager(manager, platform)

    assert manager.department == DepartmentName.MARKETING
    assert manager.current_task is None
    assert plan["supported_platforms"]


def test_manager_rejects_missing_required_input() -> None:
    """Reject incomplete task input before plan creation."""

    manager = InstagramManager()
    incomplete = build_input(ContentPlatform.INSTAGRAM)
    incomplete.pop("brand_name")
    task = TaskRecord(
        title="Create incomplete Instagram plan",
        department=DepartmentName.MARKETING,
        input_data=incomplete,
    )
    manager.accept_task(task)
    result = manager.execute_current_task()

    assert result.success is False
    assert task.status == JobStatus.FAILED
    assert "brand_name" in result.message


def test_manager_rejects_unsupported_seo_platform() -> None:
    """Prevent platform assignments from leaking between managers."""

    manager = TikTokManager()
    with pytest.raises(ValidationError):
        manager.create_platform_plan(
            brand_name="AuraAI",
            positioning="Practical education",
            target_audience="Creators",
            content_pillars=["AI workflows"],
            campaign_goal="Build awareness",
            publishing_frequency="Three times weekly",
            seo_plan=build_seo_plan(ContentPlatform.INSTAGRAM),
        )


@pytest.mark.parametrize(
    ("manager", "platform"),
    [
        (YouTubeManager(), ContentPlatform.YOUTUBE),
        (InstagramManager(), ContentPlatform.INSTAGRAM),
        (TikTokManager(), ContentPlatform.TIKTOK),
    ],
)
def test_monetization_notes_never_guarantee_earnings(
    manager,
    platform: ContentPlatform,
) -> None:
    """Keep monetization paths structured and non-guaranteed."""

    plan = execute_manager(manager, platform)
    growth = plan["growth_plan"]

    assert growth["monetization_paths"]
    assert growth["guaranteed_earnings"] is False
    assert any(
        "guarantee" in note.lower()
        for note in growth["monetization_paths"]
    )
