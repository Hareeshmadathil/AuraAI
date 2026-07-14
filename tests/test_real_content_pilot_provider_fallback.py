"""Provider routing remains optional and deterministically recoverable."""

from company_missions.real_content_pilot import (
    RealContentPilot,
    RealContentPilotResult,
    create_sample_real_content_pilot_input,
)
from providers import ProviderRegistry, ProviderRouter


def test_unavailable_provider_falls_back_without_vendor_leakage() -> None:
    router = ProviderRouter(ProviderRegistry())
    operation = RealContentPilot(provider_router=router).run(
        create_sample_real_content_pilot_input()
    )
    assert operation.success
    result = RealContentPilotResult.model_validate(
        operation.data["real_content_pilot_result"]
    )

    assert all(item.fallback_used for item in result.provider_usage_summary)
    assert {item.provider for item in result.provider_usage_summary} == {
        "deterministic"
    }
    serialized = result.model_dump_json()
    assert "api_key" not in serialized
    assert "raw_response" not in serialized


def test_live_requirement_fails_closed_without_approval_or_fallback() -> None:
    value = create_sample_real_content_pilot_input().model_copy(
        update={
            "founder_requires_live_ai": True,
            "allow_deterministic_fallback": False,
        }
    )
    result = RealContentPilot().run(value)
    assert not result.success
    assert result.error_code == "LIVE_AI_NOT_APPROVED"
