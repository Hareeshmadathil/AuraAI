"""Offline deterministic Intelligence provider."""

from __future__ import annotations

import hashlib

from intelligence.models import (
    AudiencePersona,
    CompetitorReport,
    HookAnalysis,
    SEOReport,
    ThumbnailAnalysis,
    TrendDirection,
    TrendReport,
)


class DeterministicIntelligenceProvider:
    """Generate transparent sample analysis solely from supplied text."""

    def analyze_trends(self, niche: str) -> TrendReport:
        score = self._score(niche, 68, 20)
        direction = TrendDirection.EMERGING if score >= 78 else TrendDirection.STEADY
        return TrendReport(
            niche=niche,
            direction=direction,
            opportunity_score=score,
            signals=[
                f"Educational explainers about {niche} support repeatable coverage.",
                "Practical, evidence-aware formats can serve evergreen discovery.",
            ],
            risks=["Signals are deterministic assumptions, not live trend data."],
        )

    def analyze_competitors(self, niche: str) -> CompetitorReport:
        return CompetitorReport(
            niche=niche,
            competitor_archetypes=[
                "Broad educational channels",
                "Tool-led tutorial channels",
                "Short-form tip publishers",
            ],
            content_gaps=[
                "Evidence-aware beginner workflows",
                "Clear limitations and decision checkpoints",
            ],
            differentiation_strategy=(
                "Use calm, practical systems with transparent assumptions and "
                "measurable next actions."
            ),
            saturation_score=self._score(niche, 45, 30),
        )

    def build_audience_persona(self, niche: str) -> AudiencePersona:
        return AudiencePersona(
            niche=niche,
            persona_name="Practical Evaluator",
            description=f"A time-conscious beginner evaluating {niche} safely.",
            goals=["Understand the topic", "Choose one low-risk next action"],
            pain_points=["Information overload", "Unclear implementation steps"],
            objections=["Unsupported claims", "Complex or expensive workflows"],
            content_preferences=["Structured explainers", "Checklists", "Examples"],
        )

    def build_seo_report(self, niche: str) -> SEOReport:
        normalized = " ".join(niche.lower().split())
        return SEOReport(
            niche=niche,
            primary_keyword=normalized,
            secondary_keywords=[
                f"{normalized} for beginners",
                f"{normalized} workflow",
                f"how to start {normalized}",
            ],
            search_intent="Educational problem-solving and beginner implementation.",
            title_patterns=[
                f"{niche}: A Practical Beginner System",
                f"How to Start {niche} Without Common Mistakes",
            ],
            description_guidance=(
                "State the audience problem, summarize the practical framework, "
                "and disclose that assumptions require validation."
            ),
        )

    def analyze_thumbnail(self, niche: str) -> ThumbnailAnalysis:
        return ThumbnailAnalysis(
            niche=niche,
            concepts=["Problem → System", "Three-step framework", "Before → After"],
            recommended_concept="Problem → System with one short, specific promise.",
            visual_hierarchy=["Single outcome", "Simple contrast", "Brand marker"],
            clarity_score=self._score(niche, 78, 15),
            warnings=["Concepts require rights-cleared original visual assets."],
        )

    def analyze_hooks(self, niche: str) -> HookAnalysis:
        hooks = [
            f"Most beginners make {niche} harder than it needs to be.",
            f"Before choosing a tool for {niche}, map this one workflow.",
            f"Here is a safer three-step way to evaluate {niche}.",
        ]
        return HookAnalysis(
            niche=niche,
            hooks=hooks,
            recommended_hook=hooks[1],
            pacing_guidance=[
                "Clarify the payoff in the first 15 seconds.",
                "Introduce a concrete example before abstract detail.",
            ],
            retention_risks=["Long setup", "Unqualified claims", "Repeated context"],
            retention_score=self._score(niche, 72, 18),
        )

    @staticmethod
    def _score(value: str, base: int, spread: int) -> float:
        digest = hashlib.sha256(value.casefold().encode("utf-8")).digest()
        return float(base + digest[0] % (spread + 1))
