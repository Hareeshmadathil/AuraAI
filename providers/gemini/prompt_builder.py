"""Typed structured-request builder isolated inside the Gemini adapter."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

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
            response_schema=self._response_schema(output_type.model_json_schema()),
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

    @classmethod
    def _response_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """Add deterministic object ordering required by Gemini 2.0."""

        prepared = deepcopy(schema)
        cls._add_property_ordering(prepared)
        return prepared

    @classmethod
    def _add_property_ordering(cls, schema: dict[str, Any]) -> None:
        properties = schema.get("properties")
        if isinstance(properties, dict):
            schema["propertyOrdering"] = list(properties)
            for child in properties.values():
                if isinstance(child, dict):
                    cls._add_property_ordering(child)
        items = schema.get("items")
        if isinstance(items, dict):
            cls._add_property_ordering(items)
        for keyword in ("$defs", "definitions"):
            definitions = schema.get(keyword)
            if isinstance(definitions, dict):
                for child in definitions.values():
                    if isinstance(child, dict):
                        cls._add_property_ordering(child)
        for keyword in ("anyOf", "oneOf", "allOf", "prefixItems"):
            alternatives = schema.get(keyword)
            if isinstance(alternatives, list):
                for child in alternatives:
                    if isinstance(child, dict):
                        cls._add_property_ordering(child)
