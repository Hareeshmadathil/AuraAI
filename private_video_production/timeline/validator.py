"""Timeline gap, overlap, duration, and subtitle compatibility checks."""

from __future__ import annotations

from core import ValidationError

from private_video_production.models import SubtitleCue, TimelineTrack


class TimelineValidator:
    """Reject invalid deterministic timelines before FFmpeg is invoked."""

    def validate(
        self,
        tracks: list[TimelineTrack],
        subtitles: list[SubtitleCue],
        expected_duration: float,
    ) -> None:
        by_kind = {track.kind: track for track in tracks}
        video = by_kind.get("video")
        if video is None or not video.clips:
            raise ValidationError("Timeline requires a video track.")
        clips = sorted(video.clips, key=lambda item: item.start_seconds)
        cursor = 0.0
        for clip in clips:
            if clip.start_seconds < cursor - 0.01:
                raise ValidationError("Video clips overlap illegally.")
            if clip.start_seconds > cursor + 0.05:
                raise ValidationError("Video timeline contains an unexplained gap.")
            cursor = clip.end_seconds
        if abs(cursor - expected_duration) > 0.1:
            raise ValidationError("Video timeline duration is inconsistent.")
        previous_end = 0.0
        for cue in sorted(subtitles, key=lambda item: item.sequence):
            if cue.start_seconds < previous_end - 0.01:
                raise ValidationError("Subtitle cues overlap.")
            if cue.end_seconds > expected_duration + 0.1:
                raise ValidationError("Subtitle timing exceeds the timeline.")
            previous_end = cue.end_seconds
