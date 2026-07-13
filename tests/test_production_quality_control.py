"""Quality control passing and failure-detection tests."""

from company_missions.content_production import create_content_production_pipeline
from company_missions.fixtures import create_sample_production_input
from production.models import ProductionPipelineResult, QualitySeverity
from production.quality_control import ProductionQualityController


def _package():
    pipeline, _ = create_content_production_pipeline()
    result = pipeline.run(create_sample_production_input())
    return ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    ).package


def test_quality_report_passes_complete_package_and_flags_approval() -> None:
    package = _package()
    report = ProductionQualityController().review(package)
    assert report.passed
    assert report.score_percentage > 90
    approval = next(check for check in report.checks if check.name == "Founder approval")
    assert not approval.passed
    assert approval.severity == QualitySeverity.WARNING
    assert "pending" in approval.message.casefold()


def test_quality_detects_missing_assets_bad_timing_and_guarantees() -> None:
    package = _package()
    object.__setattr__(package.visual_plan, "requests", [])
    object.__setattr__(package.storyboard.scenes[1], "start_seconds", 0.0)
    package.script.sections[0].narration += " Guaranteed revenue is certain."
    report = ProductionQualityController().review(package)
    assert not report.passed
    failed = {check.name for check in report.checks if not check.passed}
    assert "Required structured assets" in failed
    assert "Sequential scene timing" in failed
    assert "Unsupported guarantee scan" in failed
    assert report.blocking_issues
