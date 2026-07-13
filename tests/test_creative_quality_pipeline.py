from company_missions import create_review_ready_production_package
from creative_quality.models import (
    CreativeQualityPipelineResult,
    CreativeQualityStage,
    QualityGateStatus,
)
from creative_quality.pipeline import create_creative_quality_pipeline


def test_complete_pipeline_preserves_stage_order_and_employee_lifecycle() -> None:
    pipeline = create_creative_quality_pipeline()
    result = pipeline.run(create_review_ready_production_package())
    parsed = CreativeQualityPipelineResult.model_validate(
        result.data["creative_quality_pipeline_result"]
    )
    assert result.success
    assert [stage.stage for stage in parsed.stage_results[:8]] == [
        CreativeQualityStage.INTAKE,
        CreativeQualityStage.HOOK_REVIEW,
        CreativeQualityStage.STORY_REVIEW,
        CreativeQualityStage.RETENTION_REVIEW,
        CreativeQualityStage.MOTION_REVIEW,
        CreativeQualityStage.SUBTITLE_REVIEW,
        CreativeQualityStage.THUMBNAIL_REVIEW,
        CreativeQualityStage.FACTUALITY_REVIEW,
    ]
    assert parsed.quality_package.gate.status == QualityGateStatus.PASSED
    assert all(employee.current_task is None for employee in pipeline.employees)


def test_pipeline_applies_only_one_revision_cycle() -> None:
    result = create_creative_quality_pipeline(minimum_score=100).run(
        create_review_ready_production_package()
    )
    parsed = CreativeQualityPipelineResult.model_validate(
        result.data["creative_quality_pipeline_result"]
    )
    assert parsed.quality_package.gate.status == QualityGateStatus.REVISION_REQUIRED
    assert parsed.revised_production_package is not None
    assert parsed.quality_package.revision_plan.revision_count == 1
    assert parsed.quality_package.applied_revisions
