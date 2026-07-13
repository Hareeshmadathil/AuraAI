"""Optional provider routing across representative AuraAI departments."""

from agents.directors import ResearchDirector
from agents.specialists import HookArchitect, ScriptWriter
from company_missions import create_review_ready_production_package
from company_missions.fixtures import create_sample_production_input
from core import DepartmentName, MissionRecord, TaskRecord
from creative_quality.models import HookAnalysis
from intelligence.pipeline import create_intelligence_pipeline
from marketing import MarketingDirector
from production.content_brief import ContentBriefBuilder
from providers import DeterministicProvider, ProviderRegistry, ProviderRouter


def build_router() -> ProviderRouter:
    registry = ProviderRegistry()
    registry.register_provider(DeterministicProvider())
    return ProviderRouter(registry)


def build_mission(department: DepartmentName) -> MissionRecord:
    mission = MissionRecord(
        title="Build a responsible creator workflow",
        description="Plan evidence-aware educational content.",
        lead_department=department,
    )
    mission.add_objective(
        description="Create one validated plan.",
        success_metric="Approved plan",
        target_value="1",
    )
    mission.approve("Approved for provider integration testing.")
    return mission


def execute(employee, input_data: dict):
    employee.configure_provider_router(build_router())
    employee.accept_task(TaskRecord(title="Provider-assisted task", input_data=input_data))
    result = employee.execute_current_task()
    assert result.success
    assert result.data["provider_advisory"]["provider"] == "deterministic"
    return result


def test_research_and_marketing_remain_deterministic_with_optional_advice() -> None:
    execute(ResearchDirector(), {"mission": build_mission(DepartmentName.RESEARCH)})
    execute(MarketingDirector(), {"mission": build_mission(DepartmentName.MARKETING)})


def test_production_and_quality_keep_domain_outputs() -> None:
    brief = ContentBriefBuilder().build(create_sample_production_input())
    script_result = execute(ScriptWriter(), {"content_brief": brief})
    assert "video_script" in script_result.data

    script = create_review_ready_production_package().script
    review_result = execute(HookArchitect(), {"video_script": script})
    HookAnalysis.model_validate(review_result.data["hook_analysis"])


def test_intelligence_keeps_existing_provider_and_optional_router() -> None:
    employee = create_intelligence_pipeline().audience_analyst
    result = execute(employee, {"niche": "responsible AI workflows"})
    assert "audience_persona" in result.data


def test_provider_disabled_preserves_exact_legacy_shape() -> None:
    director = ResearchDirector()
    director.accept_task(
        TaskRecord(
            title="Legacy research",
            input_data={"mission": build_mission(DepartmentName.RESEARCH)},
        )
    )
    result = director.execute_current_task()
    assert "provider_advisory" not in result.data
