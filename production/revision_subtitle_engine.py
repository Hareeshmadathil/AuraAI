"""Revision-only subtitle generation with strict mobile readability."""

from __future__ import annotations

import re

from production.models import SubtitlePackage, SubtitleSegment, VoiceoverPlan
from production.subtitle_engine import SubtitleEngine


MAXIMUM_SUBTITLE_LINE_CHARACTERS = 42
MAXIMUM_SUBTITLE_CUE_CHARACTERS = 60


class ControlledRevisionSubtitleEngine(SubtitleEngine):
    """Generate synchronized cues for an explicit controlled revision."""

    def build(self, voiceover_plan: VoiceoverPlan) -> SubtitlePackage:
        segments: list[SubtitleSegment] = []
        cursor = 0.0
        index = 1
        for voice_segment in voiceover_plan.segments:
            chunks = self._chunks(voice_segment.text, maximum_words=10)
            weights = [len(chunk.replace("\n", " ")) for chunk in chunks]
            total_weight = sum(weights)
            duration = voice_segment.estimated_duration_seconds
            segment_end = cursor + duration
            for chunk_number, chunk in enumerate(chunks, start=1):
                cue_duration = duration * weights[chunk_number - 1] / total_weight
                end = (
                    segment_end
                    if chunk_number == len(chunks)
                    else cursor + cue_duration
                )
                segments.append(
                    SubtitleSegment(
                        index=index,
                        start_seconds=round(cursor, 3),
                        end_seconds=round(end, 3),
                        text=chunk,
                    )
                )
                cursor = end
                index += 1
        return SubtitlePackage(
            script_id=voiceover_plan.script_id,
            language=voiceover_plan.profile.language,
            segments=segments,
            srt_text=self._serialize(segments, srt=True),
            vtt_text="WEBVTT\n\n" + self._serialize(segments, srt=False),
        )

    @staticmethod
    def _chunks(text: str, maximum_words: int) -> list[str]:
        words = [
            part
            for word in text.split()
            for part in ControlledRevisionSubtitleEngine._split_long_word(word)
        ]
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and (
                len(candidate) > MAXIMUM_SUBTITLE_LINE_CHARACTERS
                or len(current) >= maximum_words
            ):
                lines.append(" ".join(current))
                current = []
            current.append(word)
            if re.search(r"[.!?;:]$", word):
                lines.append(" ".join(current))
                current = []
        if current:
            lines.append(" ".join(current))
        return ControlledRevisionSubtitleEngine._group_lines(lines)

    @staticmethod
    def _group_lines(lines: list[str]) -> list[str]:
        cues: list[str] = []
        index = 0
        while index < len(lines):
            cue_lines = [lines[index]]
            if index + 1 < len(lines):
                combined = f"{lines[index]} {lines[index + 1]}"
                if len(combined) <= MAXIMUM_SUBTITLE_CUE_CHARACTERS:
                    cue_lines.append(lines[index + 1])
            cues.append("\n".join(cue_lines))
            index += len(cue_lines)
        return cues

    @staticmethod
    def _split_long_word(word: str) -> list[str]:
        if len(word) <= MAXIMUM_SUBTITLE_LINE_CHARACTERS:
            return [word]
        return [
            word[index:index + MAXIMUM_SUBTITLE_LINE_CHARACTERS]
            for index in range(0, len(word), MAXIMUM_SUBTITLE_LINE_CHARACTERS)
        ]

    @staticmethod
    def _serialize(segments: list[SubtitleSegment], *, srt: bool) -> str:
        return "\n\n".join(
            ControlledRevisionSubtitleEngine._serialize_segment(
                segment,
                srt=srt,
            )
            for segment in segments
        ) + "\n"

    @staticmethod
    def _serialize_segment(segment: SubtitleSegment, *, srt: bool) -> str:
        prefix = f"{segment.index}\n" if srt else ""
        return (
            f"{prefix}"
            f"{SubtitleEngine._timestamp(segment.start_seconds, srt=srt)} --> "
            f"{SubtitleEngine._timestamp(segment.end_seconds, srt=srt)}\n"
            f"{segment.text}"
        )
