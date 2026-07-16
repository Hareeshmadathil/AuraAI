"""Secret-safe NVIDIA Nemotron configuration."""
from __future__ import annotations

from urllib.parse import urlparse
from pydantic import Field, SecretStr, model_validator
from core import AuraBaseModel

DEFAULT_NEMOTRON_BASE_URL = "https://integrate.api.nvidia.com/v1"
ALLOWED_NVIDIA_HOSTS = frozenset({"integrate.api.nvidia.com"})


class NemotronConfig(AuraBaseModel):
    """Explicit environment-derived configuration; secrets never serialize."""

    enabled: bool = False
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    model: str = "nvidia/nemotron-3-ultra"
    base_url: str = DEFAULT_NEMOTRON_BASE_URL
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    maximum_output_tokens: int = Field(default=4096, ge=1, le=65536)
    temperature: float = Field(default=0.2, ge=0, le=2)
    allow_live_requests: bool = False

    @model_validator(mode="after")
    def validate_configuration(self) -> "NemotronConfig":
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_NVIDIA_HOSTS:
            raise ValueError("Nemotron base_url must use the allowlisted NVIDIA host.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Nemotron base_url cannot contain credentials or query data.")
        if self.allow_live_requests and not self.live_ready:
            raise ValueError("Live Nemotron requests require enabled=True and an API key.")
        return self

    @property
    def api_key_value(self) -> str:
        return self.api_key.get_secret_value().strip() if self.api_key else ""

    @property
    def configured(self) -> bool:
        return bool(self.api_key_value)

    @property
    def live_ready(self) -> bool:
        return self.enabled and self.allow_live_requests and self.configured
