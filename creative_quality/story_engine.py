"""Deterministic story-flow and pacing analysis."""

from __future__ import annotations

from uuid import UUID

from creative_quality.models import StoryFlowReport, StorySectionAnalysis
from production.models import ScriptSection, VideoScript


class StoryEngine:
    """Analyze every script section without rewriting the script."""

    def analyze(self, script: VideoScript) -> StoryFlowReport:
        seen: set[str] = set()
        sections: list[StorySectionAnalysis] = []
        for index, section in enumerate(script.sections):
            fingerprint = " ".join(section.narration.lower().split()[:12])
            repeated = fingerprint in seen
            seen.add(fingerprint)
            words_per_minute = (
                len(section.narration.split())
                / section.estimated_duration_seconds
                * 60
            )
            pacing = 86.0
            weak_points: list[str] = []
            improvements: list[str] = []
            if words_per_minute > 180:
                pacing = 58.0
                weak_points.append("Information density may strain comprehension.")
                improvements.append("Add a visual pause or split the explanation.")
            elif words_per_minute < 75:
                pacing = 65.0
                weak_points.append(
                    "The section may feel slow for its information value."
                )
                improvements.append("Tighten setup language and advance the example.")
            if repeated:
                weak_points.append("Opening language repeats an earlier section.")
                improvements.append(
                    "Replace repetition with new evidence or progression."
                )
            role = self._role(index, len(script.sections), section)
            transition = 74.0 if index else 88.0
            sections.append(
                StorySectionAnalysis(
                    section_id=section.section_id,
                    section_title=section.title,
                    narrative_role=role,
                    clarity_score=82 if not weak_points else 72,
                    pacing_score=pacing,
                    relevance_score=86,
                    emotional_progression_score=78 + min(index * 2, 10),
                    transition_score=transition,
                    repetition_detected=repeated,
                    weak_points=weak_points,
                    improvements=improvements or [
                        "Bridge this section to the next viewer question."
                    ],
                )
            )
        opening = sections[0].clarity_score
        ending = sections[-1].relevance_score
        middle_values = sections[1:-1] or sections
        middle = sum(item.relevance_score for item in middle_values) / len(
            middle_values
        )
        transition = sum(item.transition_score for item in sections) / len(sections)
        total = (opening + middle + ending + transition) / 4
        reordered = self._recommended_order(script.sections)
        return StoryFlowReport(
            script_id=script.script_id,
            sections=sections,
            narrative_arc="Problem, evidence, practical application, and next step",
            opening_strength=round(opening, 2),
            middle_strength=round(middle, 2),
            ending_strength=round(ending, 2),
            transition_quality=round(transition, 2),
            total_story_score=round(total, 2),
            reordered_section_ids=reordered,
            recommendations=[
                "Use each transition to resolve one question and open the next.",
                "Keep evidence adjacent to the claim it supports.",
            ],
        )

    @staticmethod
    def _role(index: int, count: int, section: ScriptSection) -> str:
        if index == 0:
            return "opening context and promise"
        if index == count - 1:
            return "resolution and viewer next step"
        if "example" in section.title.lower():
            return "concrete proof or application"
        return "evidence and narrative progression"

    @staticmethod
    def _recommended_order(
        sections: list[ScriptSection],
    ) -> list[UUID] | None:
        evidence = [item for item in sections if "evidence" in item.title.lower()]
        if evidence and sections.index(evidence[0]) > 2:
            remaining = [item for item in sections if item is not evidence[0]]
            reordered = [remaining[0], evidence[0], *remaining[1:]]
            return [item.section_id for item in reordered]
        return None
