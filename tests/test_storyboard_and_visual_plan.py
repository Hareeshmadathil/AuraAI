"""Storyboard coverage, style, and visual plan tests."""

import pytest

from company_missions.fixtures import create_sample_production_input
from production.content_brief import ContentBriefBuilder
from production.models import AssetStatus, VideoStyle
from production.script_engine import ScriptEngine
from production.storyboard_engine import StoryboardEngine
from production.visual_plan import VisualPlanBuilder


@pytest.mark.parametrize(
    "style",
    [VideoStyle.ANIME, VideoStyle.CINEMATIC_LIVE_ACTION, VideoStyle.HYBRID],
)
def test_storyboard_covers_script_and_preserves_requested_style(style) -> None:
    value = create_sample_production_input().model_copy(update={"preferred_style": style})
    brief = ContentBriefBuilder().build(value)
    script = ScriptEngine().build(brief)
    storyboard = StoryboardEngine().build(script, brief)
    assert {scene.script_section_id for scene in storyboard.scenes} == {
        section.section_id for section in script.sections
    }
    assert all(scene.style == style for scene in storyboard.scenes)
    assert [scene.sequence_number for scene in storyboard.scenes] == list(
        range(1, len(storyboard.scenes) + 1)
    )
    assert all("living artist" in scene.negative_prompt for scene in storyboard.scenes)


def test_visual_plan_is_rights_safe_and_not_generated() -> None:
    brief = ContentBriefBuilder().build(create_sample_production_input())
    script = ScriptEngine().build(brief)
    storyboard = StoryboardEngine().build(script, brief)
    plan = VisualPlanBuilder().build(storyboard, brief.format)
    assert len(plan.requests) == len(storyboard.scenes)
    assert all(item.status == AssetStatus.NOT_GENERATED for item in plan.requests)
    assert all(item.output_path is None for item in plan.requests)
    assert len({item.request_kind for item in plan.requests}) >= 3
    assert all("licensed" in " ".join(item.rights_requirements) for item in plan.requests)
