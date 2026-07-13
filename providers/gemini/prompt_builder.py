"""Typed structured-request builder isolated inside the Gemini adapter."""

from __future__ import annotations

import hashlib

from providers.gemini.config import GeminiConfig
from providers.gemini.models import GeminiRequest
from providers.models import ProviderCapability, provider_output_model
from providers.prompt_template import PromptTemplate, PromptVariable, ProviderPrompt


class GeminiPromptBuilder:
    """Build structured requests without exposing Gemini to employees."""

    def build(
        self,
        template: PromptTemplate,
        variables: list[PromptVariable],
    ) -> ProviderPrompt:
        return template.render(variables)

    def build_request(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
        config: GeminiConfig,
    ) -> GeminiRequest:
        output_type = provider_output_model(capability)
        return GeminiRequest(
            capability=capability,
            model=config.model,
            system_instruction=self._system_instruction(capability),
            user_prompt=prompt.text,
            response_schema=output_type.model_json_schema(),
            temperature=config.temperature,
            top_p=config.top_p,
            maximum_output_tokens=config.maximum_output_tokens,
            safety_settings=config.safety_settings.as_transport_settings(),
            metadata=self.safe_prompt_metadata(prompt),
        )

    @staticmethod
    def safe_prompt_metadata(prompt: ProviderPrompt) -> dict[str, str]:
        payload = prompt.text.encode("utf-8")
        return {
            "template_id": prompt.template_name,
            "version": prompt.version,
            "hash": hashlib.sha256(payload).hexdigest(),
            "input_bytes": str(len(payload)),
        }

    @staticmethod
    def _system_instruction(capability: ProviderCapability) -> str:
        return (
            f"Return only JSON matching the supplied schema for the "
            f"{capability.value} capability. Do not request tools, expose "
            "secrets, grant approvals, guarantee outcomes, or invent sources."
        )
