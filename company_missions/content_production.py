"""Company-mission integration for deterministic content production."""

from __future__ import annotations

from agents.directors import ProductionDirector
from agents.executive import AuraCOO
from agents.specialists import (
    QualityController,
    ScriptWriter,
    ShortsEditor,
    StoryboardArtist,
    ThumbnailDesigner,
    VideoEditor,
    VoiceArtist,
)
from app.dashboard.service import DashboardService
from company_missions.models import NicheDiscoveryResult
from core import ContentPlatform, OperationResult
from intelligence.models import IntelligencePackage
from intelligence.pipeline import IntelligencePipeline, create_intelligence_pipeline
from production.models import ProductionInput
from production.pipeline import ProductionPipeline
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager


class ContentProductionMission:
    """Convert an approved strategy input into a production pipeline run."""

    def __init__(
        self,
        pipeline: ProductionPipeline,
        intelligence_pipeline: IntelligencePipeline | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.intelligence_pipeline = intelligence_pipeline or getattr(
            pipeline, "intelligence_pipeline", None
        )

    def run(
        self,
        approved_input: ProductionInput | NicheDiscoveryResult | IntelligencePackage,
        *,
        founder_approved: bool = False,
    ) -> OperationResult:
        """Run production from an explicit approved topic or niche result."""

        intelligence_package: IntelligencePackage | None = None
        if isinstance(approved_input, ProductionInput):
            production_input = approved_input
        elif isinstance(approved_input, IntelligencePackage):
            intelligence_package = approved_input
            production_input = self._from_intelligence(approved_input)
        elif self.intelligence_pipeline is not None:
            intelligence_result = self.intelligence_pipeline.run(approved_input)
            if not intelligence_result.success:
                return intelligence_result
            intelligence_package = IntelligencePackage.model_validate(
                intelligence_result.data["intelligence_package"]
            )
            production_input = self._from_intelligence(intelligence_package)
        else:
            production_input = self._from_niche_result(approved_input)
        result = self.pipeline.run(
            production_input,
            founder_approved=founder_approved,
        )
        if result.success and intelligence_package is not None:
            result.data["intelligence_package"] = (
                intelligence_package.model_dump(mode="json")
            )
        return result

    @staticmethod
    def _from_niche_result(result: NicheDiscoveryResult) -> ProductionInput:
        niche = result.selected_niche.name
        return ProductionInput(
            mission_id=result.mission_id,
            brand_name="AuraAI Practical Systems",
            topic=niche,
            working_title=f"{niche}: A Practical First System",
            target_audience="People seeking practical educational guidance",
            audience_problem=f"turning interest in {niche} into a safe first workflow",
            audience_promise="understand a responsible framework and one next action",
            content_pillars=["Practical education", "Evidence-aware implementation"],
            primary_platform=ContentPlatform.YOUTUBE,
            target_duration_seconds=240,
            language="English",
            tone="practical and evidence-aware",
            campaign_goal="Prepare a review-ready flagship educational package",
            primary_keyword=niche,
            secondary_keywords=[],
            source_notes=[*result.warnings, result.strategy_summary],
            constraints=[
                "Verify sample assumptions before publication.",
                "Do not guarantee performance or revenue.",
            ],
            preferred_call_to_action="Choose one low-risk action and document the baseline.",
            requires_founder_approval=True,
            sample_data=True,
        )

    @staticmethod
    def _from_intelligence(result: IntelligencePackage) -> ProductionInput:
        persona = result.audience_persona
        return ProductionInput(
            mission_id=result.mission_id,
            brand_name="AuraAI Practical Systems",
            topic=result.niche,
            working_title=result.seo_report.title_patterns[0],
            target_audience=persona.description,
            audience_problem=persona.pain_points[0],
            audience_promise=persona.goals[-1],
            content_pillars=[
                "Practical education",
                result.competitor_report.content_gaps[0],
            ],
            primary_platform=ContentPlatform.YOUTUBE,
            target_duration_seconds=240,
            language="English",
            tone="practical and evidence-aware",
            campaign_goal="Turn Intelligence findings into a review-ready package",
            primary_keyword=result.seo_report.primary_keyword,
            secondary_keywords=result.seo_report.secondary_keywords,
            source_notes=[
                *result.trend_report.signals,
                result.competitor_report.differentiation_strategy,
                *result.warnings,
            ],
            constraints=[
                "Validate deterministic Intelligence against live evidence.",
                "Do not guarantee savings, revenue, reach, or retention.",
            ],
            preferred_call_to_action=persona.goals[-1],
            requires_founder_approval=True,
            sample_data=result.sample_data,
        )


def create_content_production_pipeline(
    *,
    state_manager: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> tuple[
    ProductionPipeline,
    RuntimeOrchestrator,
]:
    """Create an isolated offline pipeline and runtime for local use."""

    bus = event_bus or (
        state_manager.event_bus if state_manager is not None else RuntimeEventBus()
    )
    state = state_manager or RuntimeStateManager(bus)
    coo = AuraCOO()
    runner = MissionRunner(state, bus)
    orchestrator = RuntimeOrchestrator(bus, state, coo, runner)
    intelligence_pipeline = create_intelligence_pipeline(
        state_manager=state,
        event_bus=bus,
    )
    pipeline = ProductionPipeline(
        production_director=ProductionDirector(),
        script_writer=ScriptWriter(),
        storyboard_artist=StoryboardArtist(),
        voice_artist=VoiceArtist(),
        thumbnail_designer=ThumbnailDesigner(),
        shorts_editor=ShortsEditor(),
        video_editor=VideoEditor(),
        quality_controller=QualityController(),
        runtime_orchestrator=orchestrator,
        intelligence_pipeline=intelligence_pipeline,
    )
    return pipeline, orchestrator


def create_content_production_demo_dashboard_service() -> DashboardService:
    """Build the cumulative dashboard through the Production stage."""

    from app.runtime.unified_context import DashboardContextStage
    from company_missions.unified_dashboard import (
        create_unified_dashboard_service,
    )

    return create_unified_dashboard_service(
        DashboardContextStage.PRODUCTION
    )
