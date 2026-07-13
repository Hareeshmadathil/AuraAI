"""Mobile-readable deterministic subtitle optimization."""

from __future__ import annotations

import textwrap

from creative_quality.models import SubtitleLineAnalysis, SubtitleOptimization
from production.models import SubtitlePackage, SubtitleSegment


class SubtitleQualityEngine:
    """Optimize subtitle layout in memory without writing artifacts."""

    def analyze(self, package: SubtitlePackage) -> SubtitleOptimization:
        lines: list[SubtitleLineAnalysis] = []
        srt_blocks: list[str] = []
        vtt_blocks: list[str] = ["WEBVTT", ""]
        for segment in package.segments:
            optimized = self._wrap(segment.text)
            duration = segment.end_seconds - segment.start_seconds
            actual_cps = len(segment.text.replace("\n", "")) / duration
            warnings = []
            if actual_cps > 20:
                warnings.append("Reading speed exceeds the preferred 20 CPS.")
            if segment.text.isupper() and len(segment.text) > 8:
                warnings.append("Avoid excessive all-caps subtitle text.")
            score = max(50.0, 100.0 - max(actual_cps - 17, 0) * 4)
            split_lines = optimized.splitlines()
            if len(split_lines) > 2:
                warnings.append(
                    "Split this cue to keep subtitles within two mobile lines."
                )
            highlights = [
                word.strip(".,:;!?")
                for word in segment.text.split()
                if len(word.strip(".,:;!?")) >= 8
            ][:3]
            lines.append(
                SubtitleLineAnalysis(
                    segment_index=segment.index,
                    original_text=segment.text,
                    optimized_text=optimized,
                    characters_per_line=max(len(item) for item in split_lines),
                    reading_speed_cps=round(actual_cps, 2),
                    line_count=len(split_lines),
                    keyword_highlights=highlights,
                    readability_score=round(score, 2),
                    safe_area_notes=(
                        "Keep text inside the lower-center mobile safe area with "
                        "padding."
                    ),
                    warnings=warnings,
                )
            )
            timing = (
                f"{self._timestamp(segment.start_seconds, srt=True)} --> "
                f"{self._timestamp(segment.end_seconds, srt=True)}"
            )
            srt_blocks.append(f"{segment.index}\n{timing}\n{optimized}")
            vtt_timing = (
                f"{self._timestamp(segment.start_seconds, srt=False)} --> "
                f"{self._timestamp(segment.end_seconds, srt=False)}"
            )
            vtt_blocks.append(f"{vtt_timing}\n{optimized}")
        readability = sum(item.readability_score for item in lines) / len(lines)
        timing_score = 100 - sum(bool(item.warnings) for item in lines) * 4
        emphasis = 88 if any(item.keyword_highlights for item in lines) else 76
        overall = (readability * 0.5) + (timing_score * 0.3) + (emphasis * 0.2)
        return SubtitleOptimization(
            subtitle_package_id=package.package_id,
            lines=lines,
            mobile_readability_score=round(readability, 2),
            timing_score=max(0, round(timing_score, 2)),
            emphasis_score=emphasis,
            overall_subtitle_score=round(overall, 2),
            optimized_srt_text="\n\n".join(srt_blocks) + "\n",
            optimized_vtt_text="\n\n".join(vtt_blocks) + "\n",
        )

    @staticmethod
    def _wrap(text: str) -> str:
        normalized = " ".join(text.split())
        parts = textwrap.wrap(
            normalized,
            width=38,
            break_long_words=False,
            break_on_hyphens=False,
        )
        return "\n".join(parts)

    @staticmethod
    def _timestamp(seconds: float, *, srt: bool) -> str:
        milliseconds = round(seconds * 1000)
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        whole_seconds, millis = divmod(remainder, 1000)
        separator = "," if srt else "."
        return (
            f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"
            f"{separator}{millis:03d}"
        )
