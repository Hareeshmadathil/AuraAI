"""Environment-only configuration for the multi-LLM framework."""
from __future__ import annotations
import os
from collections.abc import Mapping
from pydantic import SecretStr
from core import AuraBaseModel
from providers.gemini.config import GeminiConfig
from providers.multi_llm import ProviderRoutingMode
from providers.nemotron.config import NemotronConfig


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


class MultiLLMSettings(AuraBaseModel):
    """Complete provider policy with excluded secret fields in child models."""
    mode: ProviderRoutingMode = ProviderRoutingMode.AUTO
    default_provider: str = "gemini"
    gemini: GeminiConfig
    nemotron: NemotronConfig

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "MultiLLMSettings":
        """Read explicit process environment values without loading files."""
        values = environment if environment is not None else os.environ
        gemini_key=values.get("GEMINI_API_KEY", "").strip(); nvidia_key=values.get("NVIDIA_API_KEY", "").strip()
        return cls(mode=ProviderRoutingMode(values.get("AURAAI_LLM_ROUTING_MODE", "auto").strip().lower()),
            default_provider=values.get("AURAAI_DEFAULT_AI_PROVIDER", "gemini").strip().lower(),
            gemini=GeminiConfig(enabled=_enabled(values.get("AURAAI_GEMINI_ENABLED")),
                allow_live_requests=_enabled(values.get("AURAAI_GEMINI_ALLOW_LIVE")),
                api_key=SecretStr(gemini_key) if gemini_key else None,
                model=values.get("AURAAI_GEMINI_MODEL", "gemini-3.5-flash").strip()),
            nemotron=NemotronConfig(enabled=_enabled(values.get("AURAAI_NEMOTRON_ENABLED")),
                allow_live_requests=_enabled(values.get("AURAAI_NEMOTRON_ALLOW_LIVE")),
                api_key=SecretStr(nvidia_key) if nvidia_key else None,
                model=values.get("AURAAI_NEMOTRON_MODEL", "nvidia/nemotron-3-ultra").strip()))
