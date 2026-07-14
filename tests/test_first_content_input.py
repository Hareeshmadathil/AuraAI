"""Input contract tests for the first content mission."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from company_missions.first_real_content.dashboard import create_sample_first_content_input
from company_missions.first_real_content.models import FirstContentMissionInput


def test_valid_input_has_safe_defaults_and_no_credentials() -> None:
    value = create_sample_first_content_input()
    assert value.allow_live_gemini is False
    assert value.allow_deterministic_fallback is True
    assert value.requested_at.utcoffset() is not None
    assert not {"api_key", "credential", "authorization"} & set(FirstContentMissionInput.model_fields)


@pytest.mark.parametrize("field,value", [("topic", ""), ("target_duration_seconds", 20)])
def test_invalid_input_is_rejected(field: str, value: object) -> None:
    payload = create_sample_first_content_input().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        FirstContentMissionInput.model_validate(payload)


def test_naive_timestamp_is_rejected() -> None:
    payload = create_sample_first_content_input().model_dump()
    payload["requested_at"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        FirstContentMissionInput.model_validate(payload)
