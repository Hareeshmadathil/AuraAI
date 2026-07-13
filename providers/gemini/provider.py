"""Credential-free Gemini placeholder; it never performs network work."""

from providers.exceptions import ProviderUnavailableError
from providers.gemini.config import GeminiConfig
from providers.models import (
    ProviderCapability,
    ProviderDescriptor,
    ProviderKind,
    ProviderOutput,
)
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult


class GeminiProvider:
    """Disabled stub reserved for a separately approved live integration."""

    def __init__(self, config: GeminiConfig | None = None) -> None:
        self.config = config or GeminiConfig()
        self.descriptor = ProviderDescriptor(
            name="gemini",
            kind=ProviderKind.STUB,
            enabled=self.config.enabled,
            model=self.config.model,
            capabilities=frozenset(ProviderCapability),
        )

    def generate(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderResult[ProviderOutput]:
        del capability, prompt
        raise ProviderUnavailableError(
            "Gemini is a credential-free stub; no network request was made.",
            provider_name=self.descriptor.name,
            retryable=False,
        )
