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
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from company_missions.fixtures import create_sample_production_input
from company_missions.models import NicheDiscoveryResult
from core import ContentPlatform, OperationResult
from production.models import ProductionInput, ProductionPipelineResult
from production.pipeline import ProductionPipeline
from runtime_engine.dashboard_adapter import create_dashboard_service_from_runtime
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager


class ContentProductionMission:
    """Convert an approved strategy input into a production pipeline run."""

    def __init__(self, pipeline: ProductionPipeline) -> None:
        self.pipeline = pipeline

    def run(
        self,
        approved_input: ProductionInput | NicheDiscoveryResult,
        *,
        founder_approved: bool = False,
    ) -> OperationResult:
        """Run production from an explicit approved topic or niche result."""

        production_input = (
            approved_input
            if isinstance(approved_input, ProductionInput)
            else self._from_niche_result(approved_input)
        )
        return self.pipeline.run(
            production_input,
            founder_approved=founder_approved,
        )

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


def create_content_production_pipeline() -> tuple[
    ProductionPipeline,
    RuntimeOrchestrator,
]:
    """Create an isolated offline pipeline and runtime for local use."""

    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    coo = AuraCOO()
    runner = MissionRunner(state, bus)
    orchestrator = RuntimeOrchestrator(bus, state, coo, runner)
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
    )
    return pipeline, orchestrator


def create_content_production_demo_dashboard_service() -> DashboardService:
    """Run deterministic sample production and return a dashboard service."""

    pipeline, orchestrator = create_content_production_pipeline()
    result = ContentProductionMission(pipeline).run(
        create_sample_production_input(),
        founder_approved=False,
    )
    if not result.success:
        raise RuntimeError(result.message)
    pipeline_result = ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    )
    return create_dashboard_service_from_runtime(
        orchestrator.snapshot(),
        mode=DashboardMode.DEMO,
        data_label=(
            "PRODUCTION DEMO / DETERMINISTIC SAMPLE / PLANNED / NOT RENDERED"
        ),
        production_package=pipeline_result.package,
    )
