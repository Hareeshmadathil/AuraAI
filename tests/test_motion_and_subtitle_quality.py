from company_missions import create_review_ready_production_package
from creative_quality.motion_engine import MotionEngine
from creative_quality.subtitle_engine import SubtitleQualityEngine


def test_motion_plan_considers_every_scene_and_accessibility() -> None:
    package = create_review_ready_production_package()
    plan = MotionEngine().analyze(package.storyboard)
    assert len(plan.cues) == len(package.storyboard.scenes)
    assert all(cue.accessibility_notes for cue in plan.cues)
    assert plan.transition_strategy


def test_subtitle_output_is_mobile_readable_and_valid() -> None:
    package = create_review_ready_production_package().subtitle_package
    report = SubtitleQualityEngine().analyze(package)
    assert report.optimized_vtt_text.startswith("WEBVTT")
    assert "-->" in report.optimized_srt_text
    assert all(line.characters_per_line <= 42 for line in report.lines)
    assert all(line.line_count <= 3 for line in report.lines)
