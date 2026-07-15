"""Focused revision-only subtitle generation tests."""

from uuid import uuid4

from production.models import VoiceProfile, VoiceSegment, VoiceoverPlan
from production.revision_subtitle_engine import ControlledRevisionSubtitleEngine


def test_revision_subtitles_split_at_punctuation_without_losing_words() -> None:
    text = (
        "First proof appears on screen. Then the architecture resolves the "
        "question, and the next evidence point opens naturally."
    )
    plan = VoiceoverPlan(
        script_id=uuid4(),
        profile=VoiceProfile(
            name="Founder narration",
            language="English",
            voice_character="clear",
            pace_words_per_minute=130,
            energy_level="measured",
        ),
        segments=[
            VoiceSegment(
                scene_id=uuid4(),
                text=text,
                estimated_duration_seconds=12,
                emotion="focused",
                pause_after_seconds=0,
            )
        ],
        total_duration_seconds=12,
        output_format="wav-plan",
    )

    package = ControlledRevisionSubtitleEngine().build(plan)

    assert all(
        len(segment.text.splitlines()) <= 2 for segment in package.segments
    )
    assert all(
        len(line) <= 42
        for segment in package.segments
        for line in segment.text.splitlines()
    )
    assert " ".join(
        segment.text.replace("\n", " ") for segment in package.segments
    ).split() == text.split()
    assert package.segments[-1].end_seconds == 12
