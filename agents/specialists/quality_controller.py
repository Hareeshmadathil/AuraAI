"""Production Quality Controller employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from production.models import ProductionPackage
from production.quality_control import ProductionQualityController
from production.task_inputs import require_model


class QualityController(BaseEmployee):
    """Review production completeness, safety, and governance."""

    def __init__(self, controller: ProductionQualityController | None = None) -> None:
        super().__init__(
            name="Sentinel",
            job_title="Production Quality Controller",
            department=DepartmentName.PRODUCTION,
            description="Runs transparent production quality and approval checks.",
        )
        self.controller = controller or ProductionQualityController()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        package = require_model(task.input_data, "production_package", ProductionPackage)
        report = self.controller.review(package)
        return OperationResult.ok(
            "Quality Controller completed the production review.",
            data={"quality_report": report.model_dump(mode="json")},
        )
