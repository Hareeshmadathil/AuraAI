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

    def resolve(
        self,
        capability: ProviderCapability,
        *,
        preferred_names: tuple[str, ...] = (),
        allowed_names: frozenset[str] | None = None,
    ) -> Provider:
        providers = self.candidates(capability, preferred_names)
        for provider in providers:
            name = provider.descriptor.name
            if allowed_names is not None and name not in allowed_names:
                continue
            return provider
        raise ProviderUnavailableError(
            f"No enabled provider is registered for {capability.value}."
        )

    def candidates(
        self,
        capability: ProviderCapability,
        preferred_names: tuple[str, ...] = (),
    ) -> tuple[Provider, ...]:
        """Return enabled candidates in deterministic preference order."""

        names = self._capabilities.get(capability, [])
        rank = {name: index for index, name in enumerate(preferred_names)}
        ordered = sorted(names, key=lambda name: (rank.get(name, len(rank)), names.index(name)))
        return tuple(self._providers[name] for name in ordered if self._providers[name].descriptor.enabled)

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(provider.descriptor for provider in self._providers.values())

    def providers(self) -> tuple[Provider, ...]:
        """Return registered provider instances for safe health projection."""

        return tuple(self._providers.values())
