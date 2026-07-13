"""End-to-end deterministic ProductionPipeline tests."""

from agents.specialists import QualityController, ScriptWriter
from company_missions.content_production import create_content_production_pipeline
from company_missions.fixtures import create_sample_production_input
from core import OperationResult, TaskRecord
from production.models import (
    ProductionPipelineResult,
    ProductionQualityReport,
    ProductionStage,
)


def test_full_pipeline_is_structured_ordered_and_cleans_tasks() -> None:
    pipeline, _ = create_content_production_pipeline()
    result = pipeline.run(create_sample_production_input())
    parsed = ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    )
    assert result.success
    assert parsed.package.current_stage == ProductionStage.APPROVAL
    assert parsed.package.quality_report and parsed.package.quality_report.passed
    assert [stage.stage for stage in parsed.stage_results[:10]] == [
        ProductionStage.BRIEF,
        ProductionStage.SCRIPT,
        ProductionStage.STORYBOARD,
        ProductionStage.VOICE,
        ProductionStage.VISUAL,
        ProductionStage.THUMBNAIL,
        ProductionStage.SHORT_FORM,
        ProductionStage.SUBTITLES,
        ProductionStage.ASSEMBLY,
        ProductionStage.QUALITY_CONTROL,
    ]
    assert all(employee.current_task is None for employee in pipeline.employees)
    assert parsed.package.assembly_manifest.render_status.value == "not_rendered"
    assert all(request.output_path is None for request in parsed.package.visual_plan.requests)
    assert ProductionPipelineResult.model_validate_json(parsed.model_dump_json())


def test_pipeline_completes_when_no_founder_approval_is_required() -> None:
    pipeline, _ = create_content_production_pipeline()
    value = create_sample_production_input().model_copy(
        update={"requires_founder_approval": False}
    )
    result = pipeline.run(value)
    package = ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    ).package
    assert result.success
    assert package.current_stage == ProductionStage.COMPLETED
    assert package.completed_at is not None


class FailingScriptWriter(ScriptWriter):
    """Deterministic injected failure for stage-preservation testing."""

    def perform_task(self, task: TaskRecord) -> OperationResult:
        return OperationResult.failure("Injected script failure.")


def test_pipeline_preserves_completed_stages_after_later_failure() -> None:
    pipeline, _ = create_content_production_pipeline()
    pipeline.script_writer = FailingScriptWriter()
    result = pipeline.run(create_sample_production_input())
    assert not result.success
    assert result.data["stage_results"][0]["stage"] == "brief"
    assert result.data["stage_results"][0]["success"] is True
    assert result.data["stage_results"][1]["stage"] == "script"
    assert result.data["stage_results"][1]["success"] is False
    assert "content_brief" in result.data["completed_outputs"]
    assert pipeline.script_writer.current_task is None


class BlockingQualityController(QualityController):
    """Injected quality blocker for pipeline stop testing."""

    def perform_task(self, task: TaskRecord) -> OperationResult:
        result = super().perform_task(task)
        report = ProductionQualityReport.model_validate(result.data["quality_report"])
        report.passed = False
        report.blocking_issues = ["Injected quality blocker."]
        return OperationResult.ok(
            "Injected blocking review.",
            data={"quality_report": report.model_dump(mode="json")},
        )


def test_pipeline_stops_on_quality_blockers() -> None:
    pipeline, _ = create_content_production_pipeline()
    pipeline.quality_controller = BlockingQualityController()
    result = pipeline.run(create_sample_production_input())
    assert not result.success
    assert result.error_code == "PRODUCTION_QUALITY_BLOCKED"
    assert result.data["production_package"]["current_stage"] == "failed"
