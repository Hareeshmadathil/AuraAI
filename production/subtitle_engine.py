"""In-memory SRT and WebVTT generation."""

from __future__ import annotations

from production.models import SubtitlePackage, SubtitleSegment, VoiceoverPlan


class SubtitleEngine:
    """Create deterministic, non-overlapping subtitle cues."""

    def build(self, voiceover_plan: VoiceoverPlan) -> SubtitlePackage:
        """Split voice text into readable cues and return subtitle strings."""

        segments: list[SubtitleSegment] = []
        cursor = 0.0
        index = 1
        for voice_segment in voiceover_plan.segments:
            chunks = self._chunks(voice_segment.text, maximum_words=10)
            duration = voice_segment.estimated_duration_seconds / len(chunks)
            for chunk_number, chunk in enumerate(chunks, start=1):
                end = (
                    cursor + voice_segment.estimated_duration_seconds
                    if chunk_number == len(chunks)
                    else cursor + duration
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
        srt = "\n\n".join(
            f"{segment.index}\n{self._timestamp(segment.start_seconds, srt=True)} --> "
            f"{self._timestamp(segment.end_seconds, srt=True)}\n{segment.text}"
            for segment in segments
        ) + "\n"
        vtt = "WEBVTT\n\n" + "\n\n".join(
            f"{self._timestamp(segment.start_seconds, srt=False)} --> "
            f"{self._timestamp(segment.end_seconds, srt=False)}\n{segment.text}"
            for segment in segments
        ) + "\n"
        return SubtitlePackage(
            script_id=voiceover_plan.script_id,
            language=voiceover_plan.profile.language,
            segments=segments,
            srt_text=srt,
            vtt_text=vtt,
        )

    @staticmethod
    def _chunks(text: str, maximum_words: int) -> list[str]:
        words = text.split()
        return [
            " ".join(words[index:index + maximum_words])
            for index in range(0, len(words), maximum_words)
        ]

    @staticmethod
    def _timestamp(seconds: float, *, srt: bool) -> str:
        milliseconds = round(seconds * 1000)
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        whole_seconds, millis = divmod(remainder, 1000)
        separator = "," if srt else "."
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}{separator}{millis:03d}"
