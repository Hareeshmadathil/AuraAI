"""Strict SRT serialization for private video subtitles."""

from private_video_production.models import SubtitleCue


def serialize_srt(cues: list[SubtitleCue]) -> str:
    """Serialize validated cues in deterministic sequence order."""

    return "\n\n".join(
        f"{cue.sequence}\n{_timestamp(cue.start_seconds)} --> {_timestamp(cue.end_seconds)}\n{cue.text}"
        for cue in sorted(cues, key=lambda item: item.sequence)
    ) + "\n"


def _timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"
