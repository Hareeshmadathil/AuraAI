"""Provider prompt and response validation without retaining content."""

from __future__ import annotations

import json
import re

from providers.exceptions import ProviderValidationError
from providers.models import (
    ProviderCapability,
    ProviderOutput,
    provider_output_model,
)
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult


_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]"
)

class SafetyValidator:
    """Reject likely credentials in prompts and provider responses."""

    def validate_prompt(self, prompt: ProviderPrompt) -> None:
        if _SECRET_PATTERN.search(prompt.text):
            raise ProviderValidationError("Prompt contains credential-like data.")

    def validate_response(self, output: ProviderOutput) -> None:
        serialized = json.dumps(output.model_dump(mode="json"), sort_keys=True)
        if _SECRET_PATTERN.search(serialized):
            raise ProviderValidationError("Provider response contains unsafe data.")


class ResponseValidator:
    """Require the output model associated with the requested capability."""

    def validate(
        self,
        capability: ProviderCapability,
        result: ProviderResult[ProviderOutput],
    ) -> ProviderResult[ProviderOutput]:
        expected = provider_output_model(capability)
        if not isinstance(result.output, expected):
            raise ProviderValidationError(
                "Provider returned an output model for a different capability.",
                provider_name=result.provider,
            )
        return result
