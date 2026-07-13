from company_missions import create_review_ready_production_package
from creative_quality.retention_engine import RetentionEngine
from creative_quality.story_engine import StoryEngine


def test_story_reviews_every_section_and_detects_repetition() -> None:
    script = create_review_ready_production_package().script.model_copy(deep=True)
    duplicate = script.sections[1].model_copy(
        update={"narration": script.sections[0].narration}
    )
    script.sections[1] = duplicate
    report = StoryEngine().analyze(script)
    assert len(report.sections) == len(script.sections)
    assert report.sections[1].repetition_detected
    assert report.recommendations


def test_retention_report_is_timestamped_and_explicitly_heuristic() -> None:
    script = create_review_ready_production_package().script.model_copy(
        update={"hook": "In this video, we will cover the topic."}
    )
    report = RetentionEngine().analyze(script)
    assert report.heuristic_analysis
    assert report.risks[0].timestamp_seconds == 0
    assert report.call_to_action_timing <= report.production_duration_seconds
    assert report.pattern_interrupt_recommendations
