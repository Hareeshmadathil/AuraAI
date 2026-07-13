"""Deterministic sample inputs; these are not live market research."""

from __future__ import annotations

from core import ContentPlatform
from company_missions.models import NicheCandidateInput, NicheDiscoveryInput
from production.models import ProductionInput


def create_sample_niche_candidates() -> tuple[NicheCandidateInput, ...]:
    """Return explicitly labeled local demonstration candidates."""

    label = "Deterministic sample evidence; not live market research."
    return (
        NicheCandidateInput(
            name="AI productivity for small businesses",
            description="Practical automation education for small teams.",
            demand_score=88,
            trend_velocity_score=82,
            monetization_score=90,
            competition_score=55,
            production_difficulty_score=35,
            evidence=[label, "Sample practical-business demand signal."],
            risks=["Requires accurate, reproducible demonstrations."],
        ),
        NicheCandidateInput(
            name="Beginner personal finance education",
            description="Foundational financial literacy content.",
            demand_score=82,
            trend_velocity_score=65,
            monetization_score=88,
            competition_score=70,
            production_difficulty_score=50,
            evidence=[label, "Sample evergreen education signal."],
            risks=["Claims require strict compliance and verification."],
        ),
        NicheCandidateInput(
            name="General celebrity news",
            description="Broad entertainment news coverage.",
            demand_score=95,
            trend_velocity_score=92,
            monetization_score=45,
            competition_score=95,
            production_difficulty_score=55,
            evidence=[label, "Sample short-lived attention signal."],
            risks=["Highly competitive and dependent on breaking news."],
        ),
    )


def create_sample_niche_discovery_input() -> NicheDiscoveryInput:
    """Build the documented deterministic local pipeline input."""

    return NicheDiscoveryInput(
        mission_title="Discover AuraAI's first educational niche",
        business_goal=(
            "Select one sustainable educational niche for a local "
            "content-business demonstration."
        ),
        target_market="English-speaking small business owners and creators",
        preferred_platforms=[
            ContentPlatform.YOUTUBE,
            ContentPlatform.YOUTUBE_SHORTS,
            ContentPlatform.INSTAGRAM,
            ContentPlatform.TIKTOK,
        ],
        constraints=[
            "Use deterministic sample evidence only.",
            "Do not create accounts or publish content.",
            "Do not claim live demand or guaranteed revenue.",
        ],
        candidate_niches=list(create_sample_niche_candidates()),
    )


def create_sample_production_input() -> ProductionInput:
    """Create a clearly labelled deterministic flagship production input."""

    return ProductionInput(
        brand_name="AuraAI Practical Systems",
        topic="AI productivity for small businesses",
        working_title="AI Productivity for Small Businesses: A Safe 3-Step System",
        target_audience="Small-business owners and lean operating teams",
        audience_problem=(
            "repetitive administrative work consumes time without creating a "
            "reliable, reviewable process"
        ),
        audience_promise=(
            "leave with a responsible three-step framework for testing one workflow"
        ),
        content_pillars=[
            "Practical AI education",
            "Responsible workflow design",
            "Small-business operating systems",
        ],
        primary_platform=ContentPlatform.YOUTUBE,
        target_duration_seconds=240,
        language="English",
        tone="practical, calm, and evidence-aware",
        campaign_goal="Build trust through a useful flagship educational video",
        primary_keyword="AI productivity for small businesses",
        secondary_keywords=[
            "small business automation",
            "responsible AI workflow",
            "AI productivity system",
        ],
        source_notes=[
            "Deterministic sample input; not live market research.",
            "All performance claims require verification before publication.",
        ],
        constraints=[
            "Do not expose confidential business data.",
            "Do not guarantee savings, revenue, reach, or accuracy.",
            "Use only original or properly licensed visual assets.",
        ],
        preferred_call_to_action=(
            "Write down one repeatable workflow and its current baseline before "
            "testing any tool."
        ),
        requires_founder_approval=True,
        sample_data=True,
    )
