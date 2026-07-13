"""Voice plan and in-memory subtitle generation tests."""

import re

from company_missions.fixtures import create_sample_production_input
from production.content_brief import ContentBriefBuilder
from production.script_engine import ScriptEngine
from production.storyboard_engine import StoryboardEngine
from production.subtitle_engine import SubtitleEngine
from production.voice_plan import VoicePlanBuilder


def test_voice_segments_map_to_scenes_and_align_timing() -> None:
    value = create_sample_production_input()
    brief = ContentBriefBuilder().build(value)
    script = ScriptEngine().build(brief)
    storyboard = StoryboardEngine().build(script, brief)
    plan = VoicePlanBuilder().build(
        script, storyboard, language=value.language, tone=value.tone
    )
    assert [item.scene_id for item in plan.segments] == [
        scene.scene_id for scene in storyboard.scenes
    ]
    assert plan.total_duration_seconds == storyboard.total_duration_seconds
    assert plan.profile.provider_hint


def test_subtitles_are_valid_sequential_srt_and_vtt() -> None:
    value = create_sample_production_input()
    brief = ContentBriefBuilder().build(value)
    script = ScriptEngine().build(brief)
    storyboard = StoryboardEngine().build(script, brief)
    voice = VoicePlanBuilder().build(
        script, storyboard, language=value.language, tone=value.tone
    )
    package = SubtitleEngine().build(voice)
    assert package.vtt_text.startswith("WEBVTT\n\n")
    assert re.search(r"00:00:00,000 --> 00:00:\d{2},\d{3}", package.srt_text)
    assert [item.index for item in package.segments] == list(
        range(1, len(package.segments) + 1)
    )
    assert all(
        current.start_seconds >= previous.end_seconds
        for previous, current in zip(package.segments, package.segments[1:])
    )
