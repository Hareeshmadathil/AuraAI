"""Model validation for the founder-controlled content pilot."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from company_missions.real_content_pilot import (
    RealContentPilotInput,
    ResearchArtifact,
    create_sample_real_content_pilot_input,
)


def test_input_is_typed_serializable_and_timezone_aware() -> None:
    value = create_sample_real_content_pilot_input()
    payload = value.model_dump(mode="json")

    assert payload["sample_data"] is True
    assert value.requested_at.utcoffset() is not None
    assert "api_key" not in payload


def test_input_rejects_naive_timestamp_and_short_duration() -> None:
    source = create_sample_real_content_pilot_input().model_dump()
    source.update(
        requested_at=datetime(2026, 1, 1),
        target_duration_seconds=10,
    )
    with pytest.raises(ValidationError):
        RealContentPilotInput.model_validate(source)


def test_artifacts_are_immutable_and_contain_provider_metadata() -> None:
    from uuid import uuid4

    artifact = ResearchArtifact(
        mission_id=uuid4(),
        topic="Safe automation",
        executive_summary="A supplied-evidence synthesis.",
        audience_needs=["A reviewable workflow"],
        key_questions=["What requires verification?"],
        provider_used="deterministic_local",
        fallback_used=True,
    )
    with pytest.raises(ValidationError):
        artifact.topic = "changed"
    assert artifact.model_dump(mode="json")["fallback_used"] is True
