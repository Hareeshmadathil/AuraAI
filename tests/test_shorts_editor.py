"""Shorts Editor cross-platform adaptation tests."""

from collections import Counter

from agents.specialists import ShortsEditor
from company_missions.fixtures import create_sample_production_input
from core import ContentPlatform, TaskRecord
from production.content_brief import ContentBriefBuilder
from production.models import ShortFormPackage
from production.script_engine import ScriptEngine
from production.storyboard_engine import StoryboardEngine


def test_shorts_editor_creates_three_platform_specific_assets_each() -> None:
    brief = ContentBriefBuilder().build(create_sample_production_input())
    script = ScriptEngine().build(brief)
    storyboard = StoryboardEngine().build(script, brief)
    editor = ShortsEditor()
    task = TaskRecord(
        title="Plan derivatives",
        input_data={"video_script": script, "storyboard": storyboard},
    )
    editor.accept_task(task)
    result = editor.execute_current_task()
    package = ShortFormPackage.model_validate(result.data["short_form_package"])
    counts = Counter(item.platform for item in package.assets)
    assert counts == {
        ContentPlatform.YOUTUBE_SHORTS: 3,
        ContentPlatform.INSTAGRAM: 3,
        ContentPlatform.TIKTOK: 3,
    }
    hooks = {platform: {item.hook for item in package.assets if item.platform == platform} for platform in counts}
    assert all(len(values) == 3 for values in hooks.values())
    assert all(item.narration and item.call_to_action for item in package.assets)
    editor.clear_current_task()
    assert editor.current_task is None
