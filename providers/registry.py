"""Explicit, dependency-injected provider registry."""

from __future__ import annotations

from providers.base import Provider
from providers.exceptions import ProviderUnavailableError
from providers.models import ProviderCapability, ProviderDescriptor


class ProviderRegistry:
    """Register providers without process-global mutable state."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._capabilities: dict[ProviderCapability, list[str]] = {}

    def register_provider(self, provider: Provider, *, replace: bool = False) -> None:
        descriptor = provider.descriptor
        if descriptor.name in self._providers and not replace:
            raise ValueError(f"Provider '{descriptor.name}' is already registered.")
        if replace:
            self.unregister_provider(descriptor.name, missing_ok=True)
        self._providers[descriptor.name] = provider
        for capability in descriptor.capabilities:
            self._capabilities.setdefault(capability, []).append(descriptor.name)

    def unregister_provider(self, name: str, *, missing_ok: bool = False) -> None:
        provider = self._providers.pop(name, None)
        if provider is None:
            if missing_ok:
                return
            raise KeyError(name)
        for names in self._capabilities.values():
            if name in names:
                names.remove(name)

    def resolve(self, capability: ProviderCapability) -> Provider:
        for name in self._capabilities.get(capability, []):
            provider = self._providers[name]
            if provider.descriptor.enabled:
                return provider
        raise ProviderUnavailableError(
            f"No enabled provider is registered for {capability.value}."
        )

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(provider.descriptor for provider in self._providers.values())
