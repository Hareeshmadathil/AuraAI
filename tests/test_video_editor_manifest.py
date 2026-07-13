"""Video assembly manifest tests."""

from agents.specialists import VideoEditor
from company_missions.content_production import create_content_production_pipeline
from company_missions.fixtures import create_sample_production_input
from core import TaskRecord
from production.models import RenderStatus, TrackType, VideoAssemblyManifest


def test_manifest_has_dimensions_tracks_alignment_and_safe_path() -> None:
    pipeline, _ = create_content_production_pipeline()
    result = pipeline.run(create_sample_production_input())
    manifest_data = result.data["production_pipeline_result"]["package"]["assembly_manifest"]
    manifest = VideoAssemblyManifest.model_validate(manifest_data)
    assert (manifest.width, manifest.height) == (1920, 1080)
    assert manifest.render_status == RenderStatus.NOT_RENDERED
    assert manifest.duration_seconds == 240
    assert {item.track_type for item in manifest.track_items} == set(TrackType)
    assert "/" not in manifest.output_filename and "\\" not in manifest.output_filename
    assert ".." not in manifest.output_directory


def test_video_editor_rejects_missing_inputs() -> None:
    editor = VideoEditor()
    task = TaskRecord(title="Invalid manifest", input_data={})
    editor.accept_task(task)
    result = editor.execute_current_task()
    assert not result.success
    editor.clear_current_task()
