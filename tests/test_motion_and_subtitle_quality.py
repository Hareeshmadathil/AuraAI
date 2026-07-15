from uuid import uuid4

from company_missions import create_review_ready_production_package
from creative_quality.motion_engine import MotionEngine
from creative_quality.subtitle_engine import (
    MAXIMUM_SUBTITLE_LINE_CHARACTERS,
    SubtitleQualityEngine,
)
from production.models import SubtitlePackage, SubtitleSegment


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


def _subtitle_package(*texts: str) -> SubtitlePackage:
    segments = [
        SubtitleSegment(
            index=index,
            start_seconds=float((index - 1) * 10),
            end_seconds=float(index * 10),
            text=text,
        )
        for index, text in enumerate(texts, start=1)
    ]
    return SubtitlePackage(
        script_id=uuid4(),
        language="English",
        segments=segments,
        srt_text="placeholder",
        vtt_text="WEBVTT\n\nplaceholder",
    )


def test_subtitle_line_allows_exactly_42_characters() -> None:
    text = "x" * MAXIMUM_SUBTITLE_LINE_CHARACTERS
    line = SubtitleQualityEngine().analyze(_subtitle_package(text)).lines[0]

    assert line.optimized_text == text
    assert line.characters_per_line == 42
    assert line.line_count == 1


def test_subtitle_line_splits_43_character_token_before_validation() -> None:
    text = "x" * (MAXIMUM_SUBTITLE_LINE_CHARACTERS + 1)
    line = SubtitleQualityEngine().analyze(_subtitle_package(text)).lines[0]

    assert line.characters_per_line == 42
    assert [len(value) for value in line.optimized_text.splitlines()] == [42, 1]
    assert "".join(line.optimized_text.splitlines()) == text


def test_very_long_sentence_preserves_word_order_and_line_limit() -> None:
    text = " ".join(f"word{index}" for index in range(1, 31))
    line = SubtitleQualityEngine().analyze(_subtitle_package(text)).lines[0]

    assert all(
        len(value) <= MAXIMUM_SUBTITLE_LINE_CHARACTERS
        for value in line.optimized_text.splitlines()
    )
    assert line.optimized_text.replace("\n", " ") == text


def test_subtitle_wrapping_prefers_punctuation_boundary() -> None:
    text = (
        "This opening makes one clear point, before the next idea "
        "continues with useful context."
    )
    line = SubtitleQualityEngine().analyze(_subtitle_package(text)).lines[0]

    assert line.optimized_text.splitlines()[0].endswith(",")
    assert line.optimized_text.replace("\n", " ") == text


def test_multiple_subtitle_blocks_keep_order_and_timing() -> None:
    texts = (
        "First subtitle block remains in sequence.",
        "Second subtitle block is deliberately longer, so it wraps safely.",
        "Third subtitle block closes the ordered set.",
    )
    package = _subtitle_package(*texts)
    report = SubtitleQualityEngine().analyze(package)

    assert [line.segment_index for line in report.lines] == [1, 2, 3]
    assert [line.original_text for line in report.lines] == list(texts)
    assert [
        (segment.start_seconds, segment.end_seconds)
        for segment in package.segments
    ] == [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]
    assert all(line.characters_per_line <= 42 for line in report.lines)
