"""Narration-timed subtitles reusing AuraAI's improved wrapping logic."""

from __future__ import annotations

from production.revision_subtitle_engine import ControlledRevisionSubtitleEngine

from private_video_production.models import SubtitleCue


class PrivateSubtitleBuilder:
    """Scale approved narration words to real synthesized audio duration."""

    def build(
        self,
        source_segments: list[dict[str, object]],
        narration_duration_seconds: float,
    ) -> list[SubtitleCue]:
        text = " ".join(
            str(segment.get("text", "")).replace("\n", " ")
            for segment in source_segments
        ).strip()
        chunks = ControlledRevisionSubtitleEngine._chunks(text, maximum_words=10)
        weights = [max(1, len(chunk.replace("\n", ""))) for chunk in chunks]
        total = sum(weights)
        cursor = 0.0
        cues: list[SubtitleCue] = []
        for sequence, (chunk, weight) in enumerate(zip(chunks, weights), start=1):
            end = (
                narration_duration_seconds
                if sequence == len(chunks)
                else cursor + narration_duration_seconds * weight / total
            )
            duration = end - cursor
            characters = len(chunk.replace("\n", ""))
            cues.append(
                SubtitleCue(
                    cue_id=f"cue-{sequence:04d}",
                    sequence=sequence,
                    start_seconds=round(cursor, 3),
                    end_seconds=round(end, 3),
                    text=chunk,
                    characters_per_second=round(characters / duration, 2),
                )
            )
            cursor = end
        return cues
