"""Subtitle readability and deterministic timeline regression tests."""

from pathlib import Path

import pytest

from core import ValidationError
from private_video_production.loader import MissionZeroPackageLoader
from private_video_production.scenes import MissionZeroScenePlanner
from private_video_production.subtitles import PrivateSubtitleBuilder, serialize_srt
from private_video_production.timeline import PrivateTimelineBuilder, TimelineValidator


PACKAGE = Path("outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a")


def test_subtitles_preserve_words_and_mobile_readability(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    cues = PrivateSubtitleBuilder().build(value.source_subtitles, 510)
    source_words = " ".join(str(item["text"]).replace("\n", " ") for item in value.source_subtitles).split()
    output_words = " ".join(cue.text.replace("\n", " ") for cue in cues).split()

    assert output_words == source_words
    assert all(len(line) <= 42 for cue in cues for line in cue.text.splitlines())
    assert all(len(cue.text.splitlines()) <= 2 for cue in cues)
    assert all(cue.characters_per_second <= 20 for cue in cues)
    assert cues[-1].end_seconds == 510
    assert "00:00:00,000 -->" in serialize_srt(cues)


def test_timeline_is_contiguous_deterministic_and_marked(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    scenes, _ = MissionZeroScenePlanner().plan(value)
    subtitles = PrivateSubtitleBuilder().build(value.source_subtitles, 510)
    builder = PrivateTimelineBuilder()
    first = builder.build(scenes, subtitles, None)
    second = builder.build(scenes, subtitles, None)

    assert first == second
    tracks, _, markers = first
    TimelineValidator().validate(tracks, subtitles, 510)
    assert markers[-1].kind == "founder_review"
    assert "NOT PUBLISHED" in markers[-1].label


def test_timeline_rejects_illegal_overlap(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    scenes, _ = MissionZeroScenePlanner().plan(value)
    subtitles = PrivateSubtitleBuilder().build(value.source_subtitles, 510)
    tracks, _, _ = PrivateTimelineBuilder().build(scenes, subtitles, None)
    tracks[0].clips[1].start_seconds = 0

    with pytest.raises(ValidationError, match="overlap"):
        TimelineValidator().validate(tracks, subtitles, 510)
