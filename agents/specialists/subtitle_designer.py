"""Subtitle Designer employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.subtitle_engine import SubtitleQualityEngine
from creative_quality.task_inputs import require_model
from production.models import SubtitlePackage


class SubtitleDesigner(BaseEmployee):
    """Optimize subtitle layout without writing artifact files."""

    def __init__(self, engine: SubtitleQualityEngine | None = None) -> None:
        super().__init__(
            name="Caption",
            job_title="Subtitle Designer",
            department=DepartmentName.CREATIVE_QUALITY,
            description=(
                "Optimizes subtitle timing, layout, and mobile readability."
            ),
        )
        self.engine = engine or SubtitleQualityEngine()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return in-memory optimized SRT, VTT, and line metadata."""

        package = require_model(
            task.input_data, "subtitle_package", SubtitlePackage
        )
        report = self.engine.analyze(package)
        return OperationResult.ok(
            "Subtitle Designer completed in-memory subtitle optimization.",
            data={"subtitle_optimization": report.model_dump(mode="json")},
        )
