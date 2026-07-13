from company_missions.content_production import (
    ContentProductionMission,
    create_content_production_pipeline,
)
from company_missions.models import NicheDiscoveryResult, NicheDiscoveryStageResult
from agents.specialists import TrendOpportunity
from core import DepartmentName, utc_now
from uuid import uuid4
from intelligence.models import IntelligencePackage


def test_intelligence_package_feeds_production_without_network_calls() -> None:
    production_pipeline, _ = create_content_production_pipeline()
    intelligence = production_pipeline.intelligence_pipeline.run(
        "AI productivity for small businesses"
    )
    package = IntelligencePackage.model_validate(
        intelligence.data["intelligence_package"]
    )

    result = ContentProductionMission(production_pipeline).run(
        package,
        founder_approved=False,
    )

    assert result.success is True
    assert "intelligence_package" in result.data
    production = result.data["production_pipeline_result"]["package"]
    assert production["input"]["primary_keyword"] == (
        package.seo_report.primary_keyword
    )


def test_research_result_routes_through_intelligence_before_production() -> None:
    opportunity = TrendOpportunity(
        candidate_id=uuid4(),
        name="Responsible creator automation",
        opportunity_score=82,
        rank=1,
        recommendation="Prioritize for deterministic validation.",
        score_breakdown={"demand": 82},
    )
    now = utc_now()
    discovery = NicheDiscoveryResult(
        mission_id=uuid4(),
        selected_niche=opportunity,
        ranked_candidates=[opportunity],
        research_plan_id=uuid4(),
        strategy_summary="Validate a practical education position.",
        marketing_readiness=True,
        confidence_score=0.82,
        stages=[
            NicheDiscoveryStageResult(
                stage_name="research",
                success=True,
                employee_name="Research Director",
                department=DepartmentName.RESEARCH,
                started_at=now,
                completed_at=now,
            )
        ],
        completed_at=now,
    )
    production_pipeline, _ = create_content_production_pipeline()

    result = ContentProductionMission(production_pipeline).run(discovery)

    assert result.success is True
    intelligence = IntelligencePackage.model_validate(
        result.data["intelligence_package"]
    )
    assert intelligence.mission_id == discovery.mission_id
    assert intelligence.niche == discovery.selected_niche.name
