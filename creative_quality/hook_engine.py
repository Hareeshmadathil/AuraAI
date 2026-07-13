"""Deterministic, topic-aware opening-hook analysis."""

from __future__ import annotations

import re

from creative_quality.models import HookAnalysis
from production.models import VideoScript


class HookEngine:
    """Review opening language with transparent editorial heuristics."""

    _GENERIC = ("in this video", "today we will", "welcome back", "let's talk")
    _DECEPTIVE = ("you won't believe", "secret they don't want", "guaranteed")
    _ABSOLUTE = re.compile(
        r"\b(guarantee(?:d)?|always|never fails?|instant(?:ly)?|risk[- ]free)\b",
        re.IGNORECASE,
    )

    def analyze(self, script: VideoScript) -> HookAnalysis:
        """Return one reproducible review without claiming audience prediction."""

        hook = " ".join(script.hook.split())
        lowered = hook.lower()
        generic = any(phrase in lowered for phrase in self._GENERIC)
        deceptive = any(phrase in lowered for phrase in self._DECEPTIVE)
        verification = (
            [hook] if self._ABSOLUTE.search(hook) else []
        )
        clarity = self._bounded(92 - max(len(hook) - 140, 0) * 0.2)
        relevance = 92 if script.primary_keyword.lower() in lowered else 76
        curiosity = 60 if generic else (52 if deceptive else 84)
        credibility = 48 if verification or deceptive else 88
        emotion = 68 if generic else 80
        weaknesses: list[str] = []
        recommendations: list[str] = []
        if generic:
            weaknesses.append("The opening delays the viewer-specific value.")
            recommendations.append(
                "Lead with the audience problem and useful contrast."
            )
        if deceptive:
            weaknesses.append("The opening uses a misleading clickbait pattern.")
            recommendations.append(
                "Replace sensational language with a truthful open loop."
            )
        if verification:
            weaknesses.append("The opening contains an unsupported absolute claim.")
            recommendations.append(
                "Qualify the outcome and verify it before publication."
            )
        improved = (
            f"Before you act on {script.primary_keyword}, compare what the "
            "evidence supports, where the limits are, and the practical first "
            "step you can test for yourself."
        )
        return HookAnalysis(
            original_hook=hook,
            hook_type="problem-led evidence open loop",
            clarity_score=clarity,
            curiosity_score=curiosity,
            relevance_score=relevance,
            credibility_score=credibility,
            emotional_score=emotion,
            first_five_seconds_score=round((clarity + relevance) / 2, 2),
            first_fifteen_seconds_score=round(
                (clarity + relevance + curiosity + credibility) / 4, 2
            ),
            open_loops=[
                "What does the evidence support?",
                "Which practical first step is worth testing?",
            ],
            weaknesses=weaknesses,
            recommendations=recommendations,
            improved_hook=improved,
            claims_requiring_verification=verification,
        )

    @staticmethod
    def _bounded(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)
