"""Clearly labelled deterministic fixtures for the Real Content Pilot."""

from core import ContentPlatform

from company_missions.real_content_pilot.inputs import RealContentPilotInput
from company_missions.real_content_pilot.pipeline import RealContentPilot


def create_sample_real_content_pilot_input() -> RealContentPilotInput:
    """Return a useful offline founder-review demonstration input."""

    return RealContentPilotInput(
        title="Build a practical AI workflow pilot",
        objective=(
            "Create an evidence-aware YouTube script and quality package "
            "for explicit founder review."
        ),
        topic="AI productivity for small businesses",
        target_audience="Small-business owners with lean operating teams",
        audience_problem=(
            "Repetitive administration consumes time without a documented, "
            "reviewable workflow."
        ),
        audience_promise=(
            "Understand a safe three-step method for testing one workflow."
        ),
        primary_platform=ContentPlatform.YOUTUBE,
        language="English",
        tone="practical, calm, and evidence-aware",
        target_duration_seconds=240,
        content_goal="Build trust through a useful educational pilot",
        source_notes=[
            "Founder-supplied deterministic note; not independent research.",
            "All performance claims require verification before publication.",
        ],
        constraints=[
            "Do not guarantee savings, revenue, reach, or accuracy.",
            "Do not use confidential business data.",
        ],
        primary_keyword="AI productivity for small businesses",
        secondary_keywords=[
            "small business automation",
            "responsible AI workflow",
        ],
        founder_requires_live_ai=False,
        allow_deterministic_fallback=True,
        sample_data=True,
    )


def run_deterministic_real_content_pilot():
    """Run the offline fixture to founder review without any network client."""

    pilot = RealContentPilot()
    operation = pilot.run(create_sample_real_content_pilot_input())
    if not operation.success:
        raise RuntimeError(operation.message)
    from company_missions.real_content_pilot.models import RealContentPilotResult

    return pilot, RealContentPilotResult.model_validate(
        operation.data["real_content_pilot_result"]
    )
