"""Runtime visibility and failure-health tests for production."""

from agents.specialists import ScriptWriter
from company_missions.content_production import create_content_production_pipeline
from company_missions.fixtures import create_sample_production_input
from core import OperationResult, TaskRecord
from runtime_engine.models import RuntimeEventType


def test_runtime_registers_employees_and_orders_production_events() -> None:
    pipeline, orchestrator = create_content_production_pipeline()
    result = pipeline.run(create_sample_production_input())
    snapshot = orchestrator.snapshot()
    assert result.success
    assert len(snapshot.employees) == 8
    assert all(employee.department.value == "production" for employee in snapshot.employees)
    production_events = [
        event for event in snapshot.recent_events
        if event.event_type.value.startswith("production_")
    ]
    assert production_events[0].event_type == RuntimeEventType.PRODUCTION_STAGE_STARTED
    assert production_events[-1].event_type == RuntimeEventType.PRODUCTION_PACKAGE_READY
    assert any(
        event.metadata.get("stage") == "script"
        and event.event_type == RuntimeEventType.PRODUCTION_STAGE_COMPLETED
        for event in production_events
    )
    assert snapshot.system_health["production_pipeline"].status == "operational"
    assert snapshot.statistics.production_packages == 1
    assert snapshot.production_packages[0].media_rendered is False
    assert snapshot.production_packages[0].current_stage == "approval"


class RuntimeFailingWriter(ScriptWriter):
    def perform_task(self, task: TaskRecord) -> OperationResult:
        return OperationResult.failure("Runtime-visible production failure.")


def test_runtime_reflects_production_failure() -> None:
    pipeline, orchestrator = create_content_production_pipeline()
    pipeline.script_writer = RuntimeFailingWriter()
    result = pipeline.run(create_sample_production_input())
    snapshot = orchestrator.snapshot()
    assert not result.success
    assert snapshot.system_health["production_pipeline"].status == "degraded"
    assert any(
        event.event_type == RuntimeEventType.PRODUCTION_STAGE_FAILED
        for event in snapshot.recent_events
    )
