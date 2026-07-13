"""Explicit Gemini configuration and secret-handling tests."""

import pytest
from pydantic import SecretStr, ValidationError

from providers.gemini import GeminiConfig


def test_gemini_is_disabled_and_not_live_by_default() -> None:
    config = GeminiConfig()
    assert config.enabled is False
    assert config.allow_live_requests is False
    assert config.configured is False
    assert config.live_ready is False
    assert config.model == "gemini-3.5-flash"


def test_live_configuration_requires_all_explicit_gates() -> None:
    with pytest.raises(ValidationError, match="enabled=True"):
        GeminiConfig(allow_live_requests=True, api_key=SecretStr("fake-key"))
    with pytest.raises(ValidationError, match="injected API key"):
        GeminiConfig(enabled=True, allow_live_requests=True)
    config = GeminiConfig(
        enabled=True,
        allow_live_requests=True,
        api_key=SecretStr("fake-test-key"),
    )
    assert config.live_ready is True


def test_api_key_is_excluded_from_repr_and_serialization() -> None:
    config = GeminiConfig(api_key=SecretStr("fake-sensitive-test-key"))
    assert "fake-sensitive-test-key" not in repr(config)
    assert "api_key" not in config.model_dump()
    assert "fake-sensitive-test-key" not in config.model_dump_json()


@pytest.mark.parametrize(
    "values",
    [
        {"timeout_seconds": 0},
        {"maximum_retries": -1},
        {"model": "invalid model"},
        {"base_url": "http://generativelanguage.googleapis.com/v1beta"},
        {"base_url": "https://example.com/v1beta"},
    ],
)
def test_invalid_configuration_fails_safely(values: dict) -> None:
    with pytest.raises(ValidationError):
        GeminiConfig(**values)
