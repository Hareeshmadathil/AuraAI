from company_missions import (
    ContentQualityMission,
    create_content_quality_pipeline,
    create_review_ready_production_package,
)
from creative_quality.models import CreativeQualityPipelineResult
from production.models import ProductionPackage


def test_production_package_flows_additively_into_quality() -> None:
    package = create_review_ready_production_package()
    result = ContentQualityMission(create_content_quality_pipeline()).run(package)
    parsed = CreativeQualityPipelineResult.model_validate(
        result.data["creative_quality_pipeline_result"]
    )
    assert parsed.original_production_package == package
    assert parsed.quality_package.production_package_id == package.package_id
    assert ProductionPackage.model_validate(package.model_dump()) == package


def test_legacy_production_package_remains_quality_optional() -> None:
    package = create_review_ready_production_package()
    assert package.model_fields_set
    assert "creative_quality" not in ProductionPackage.model_fields
