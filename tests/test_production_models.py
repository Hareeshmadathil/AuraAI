"""Validation and artifact-store tests for Production v1 models."""

from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from company_missions.content_production import create_content_production_pipeline
from company_missions.fixtures import create_sample_production_input
from core import StorageError, ValidationError
from production.artifact_store import ArtifactStore
from production.models import (
    ContentBrief,
    ProductionInput,
    ProductionPipelineResult,
    Storyboard,
    VideoAssemblyManifest,
)


def _result() -> ProductionPipelineResult:
    pipeline, _ = create_content_production_pipeline()
    result = pipeline.run(create_sample_production_input())
    assert result.success
    return ProductionPipelineResult.model_validate(
        result.data["production_pipeline_result"]
    )


def test_models_serialize_and_use_aware_timestamps() -> None:
    result = _result()
    assert result.package.created_at.utcoffset() is not None
    assert ProductionPipelineResult.model_validate_json(
        result.model_dump_json()
    ).package.package_id == result.package.package_id


def test_invalid_duration_and_naive_timestamp_are_rejected() -> None:
    data = create_sample_production_input().model_dump()
    data["target_duration_seconds"] = -1
    with pytest.raises(PydanticValidationError):
        ProductionInput.model_validate(data)
    brief_data = _result().package.brief.model_dump()
    brief_data["created_at"] = datetime(2026, 1, 1)
    with pytest.raises(PydanticValidationError):
        ContentBrief.model_validate(brief_data)


def test_storyboard_rejects_nonsequential_or_overlapping_scenes() -> None:
    data = _result().package.storyboard.model_dump()
    data["scenes"][1]["sequence_number"] = 4
    with pytest.raises(PydanticValidationError):
        Storyboard.model_validate(data)
    data = _result().package.storyboard.model_dump()
    data["scenes"][1]["start_seconds"] = 0
    with pytest.raises(PydanticValidationError):
        Storyboard.model_validate(data)


def test_manifest_rejects_unsafe_filename_and_directory() -> None:
    data = _result().package.assembly_manifest.model_dump()
    data["output_filename"] = "../escape.mp4"
    with pytest.raises(PydanticValidationError):
        VideoAssemblyManifest.model_validate(data)
    data = _result().package.assembly_manifest.model_dump()
    data["output_directory"] = "../outside"
    with pytest.raises(PydanticValidationError):
        VideoAssemblyManifest.model_validate(data)


def test_artifact_store_is_explicit_safe_and_atomic(tmp_path) -> None:
    memory = ArtifactStore(in_memory=True)
    reference = memory.save_model("package", {"safe": True})
    assert b'"safe": true' in memory.read_memory_artifact(reference)
    with pytest.raises(StorageError):
        memory.save_model("package", {"safe": True})
    with pytest.raises(ValidationError):
        memory.save_script("../secret", "blocked")

    root = tmp_path / "artifacts"
    store = ArtifactStore(root)
    assert not root.exists()
    saved = store.save_srt("captions", "1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    assert root.exists()
    assert (root / saved.name).read_text(encoding="utf-8").startswith("1")
    assert not list(root.glob("*.tmp"))
