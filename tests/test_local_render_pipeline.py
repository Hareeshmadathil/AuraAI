from pathlib import Path

from company_missions.local_render_pilot import create_review_ready_production_package
from production.rendering.models import RenderSettings
from production.rendering.pipeline import LocalRenderPipeline, build_local_render_pipeline
from runtime_engine.event_bus import RuntimeEventBus


class Detector:
    def detect(self):
        raise AssertionError("Approval must be checked before capability detection.")


def test_pipeline_blocks_without_founder_render_approval(tmp_path: Path) -> None:
    bus = RuntimeEventBus()
    pipeline = LocalRenderPipeline(capability_detector=Detector(), export_service=object(), event_bus=bus)
    result = pipeline.run(create_review_ready_production_package(), RenderSettings(output_root=tmp_path))
    assert result.success is False
    assert result.error_code == "FOUNDER_RENDER_APPROVAL_REQUIRED"


def test_pipeline_factory_has_no_import_time_capability_run(tmp_path: Path) -> None:
    pipeline = build_local_render_pipeline(RenderSettings(output_root=tmp_path))
    assert isinstance(pipeline, LocalRenderPipeline)
