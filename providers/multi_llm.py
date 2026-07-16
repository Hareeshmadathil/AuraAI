"""Routing policy for vendor-independent text reasoning providers."""
from enum import StrEnum


class ProviderRoutingMode(StrEnum):
    """Founder-configured provider selection modes."""

    AUTO = "auto"
    GEMINI_ONLY = "gemini_only"
    NEMOTRON_ONLY = "nemotron_only"

    @property
    def provider_order(self) -> tuple[str, ...]:
        return {
            self.AUTO: (),
            self.GEMINI_ONLY: ("gemini",),
            self.NEMOTRON_ONLY: ("nemotron",),
        }[self]
