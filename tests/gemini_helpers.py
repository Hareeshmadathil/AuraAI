"""Mock-only Gemini response builders; no network behavior."""

from __future__ import annotations

import json

from providers import DeterministicProvider, ProviderCapability
from providers.gemini import GeminiTransportResponse
from providers.prompt_template import PromptCategory, build_department_prompt


def prompt_for(capability: ProviderCapability):
    return build_department_prompt(
        f"gemini_{capability.value}_test",
        PromptCategory.RESEARCH,
        "responsible creator guidance",
    )


def response_for(
    request,
    *,
    status_code: int = 200,
    fenced: bool = False,
    payload: dict | None = None,
    finish_reason: str = "STOP",
) -> GeminiTransportResponse:
    output = payload or DeterministicProvider().generate(
        request.capability,
        prompt_for(request.capability),
    ).output.model_dump(mode="json")
    text = json.dumps(output)
    if fenced:
        text = f"```json\n{text}\n```"
    body = json.dumps(
        {
            "candidates": [
                {
                    "content": {"parts": [{"text": text}]},
                    "finishReason": finish_reason,
                    "safetyRatings": [],
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 12,
                "candidatesTokenCount": 8,
            },
        }
    )
    return GeminiTransportResponse(
        request_id=request.request_id,
        status_code=status_code,
        response_body=body,
        latency_ms=4.5,
    )
