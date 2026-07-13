"""Explicit, secret-safe configuration for the opt-in Gemini adapter."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator

from core import AuraBaseModel
from providers.gemini.safety import GeminiSafetyConfig


DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
ALLOWED_GEMINI_HOSTS = frozenset({"generativelanguage.googleapis.com"})


class GeminiConfig(AuraBaseModel):
    """Configuration supplied explicitly; the API key is never serialized."""

    enabled: bool = False
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    model: str = Field(default="gemini-3.5-flash", pattern=r"^[A-Za-z0-9._-]+$")
    base_url: str = DEFAULT_GEMINI_BASE_URL
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    maximum_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.25, ge=0, le=10)
    temperature: float = Field(default=0.2, ge=0, le=2)
    top_p: float = Field(default=0.9, gt=0, le=1)
    maximum_output_tokens: int = Field(default=2048, ge=1, le=65536)
    safety_settings: GeminiSafetyConfig = Field(
        default_factory=GeminiSafetyConfig
    )
    allow_live_requests: bool = False
    redact_prompts: bool = True
    redact_responses: bool = True
    fallback_enabled: bool = True
    cache_enabled: bool = False
    request_budget: int | None = Field(default=None, ge=1)
    daily_request_limit: int | None = Field(default=None, ge=1)
    sample_data: bool = False

    @model_validator(mode="after")
    def validate_live_configuration(self) -> "GeminiConfig":
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_GEMINI_HOSTS:
            raise ValueError("Gemini base_url must use the allowlisted HTTPS host.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "Gemini base_url cannot contain credentials or query data."
            )
        if self.allow_live_requests and not self.enabled:
            raise ValueError("Live Gemini requests require enabled=True.")
        if self.allow_live_requests and not self.api_key_value:
            raise ValueError("Live Gemini requests require an injected API key.")
        return self

    @property
    def api_key_value(self) -> str:
        if self.api_key is None:
            return ""
        return self.api_key.get_secret_value().strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key_value)

    @property
    def live_ready(self) -> bool:
        return self.enabled and self.allow_live_requests and self.configured
