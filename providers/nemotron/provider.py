"""NVIDIA Nemotron 3 Ultra adapter using the common Provider interface."""
from __future__ import annotations
from time import perf_counter
from core import utc_now
from providers.exceptions import ProviderUnavailableError
from providers.models import ProviderCapability, ProviderDescriptor, ProviderHealth, ProviderKind, ProviderOutput, provider_output_model
from providers.nemotron.config import NemotronConfig
from providers.nemotron.models import NemotronRequest
from providers.nemotron.transport import NemotronTransport, UnavailableNemotronTransport
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult
from providers.usage import ProviderUsage

SUPPORTED_NEMOTRON_CAPABILITIES = frozenset({ProviderCapability.REASONING, ProviderCapability.PLANNING,
    ProviderCapability.SUMMARIZATION, ProviderCapability.CODING, ProviderCapability.REWRITING,
    ProviderCapability.STRUCTURED_JSON, ProviderCapability.LONG_CONTEXT})


class NemotronProvider:
    """Generate typed provider-neutral results through an injected transport."""
    def __init__(self, config: NemotronConfig | None = None, transport: NemotronTransport | None = None) -> None:
        self.config = config or NemotronConfig(); self.transport = transport or UnavailableNemotronTransport()
        self.descriptor = ProviderDescriptor(name="nemotron", kind=ProviderKind.REMOTE, enabled=self.config.enabled,
            model=self.config.model, capabilities=SUPPORTED_NEMOTRON_CAPABILITIES)
        self._requests=0; self._successes=0; self._failures=0

    def check_ready(self) -> None:
        if not self.config.live_ready:
            raise ProviderUnavailableError("Nemotron is unavailable; safe fallback remains active.", provider_name="nemotron", retryable=False)

    def generate(self, capability: ProviderCapability, prompt: ProviderPrompt) -> ProviderResult[ProviderOutput]:
        self.check_ready()
        if capability not in SUPPORTED_NEMOTRON_CAPABILITIES:
            raise ProviderUnavailableError("Nemotron does not support this capability.", provider_name="nemotron", retryable=False)
        request = NemotronRequest(capability=capability, prompt=prompt.text, model=self.config.model,
            response_schema=provider_output_model(capability).model_json_schema(), maximum_output_tokens=self.config.maximum_output_tokens,
            temperature=self.config.temperature)
        started_at=utc_now(); started=perf_counter(); self._requests += 1
        try: response=self.transport.send(request, timeout_seconds=self.config.timeout_seconds)
        except Exception: self._failures += 1; raise
        output=provider_output_model(capability).model_validate(response.payload); self._successes += 1
        usage=ProviderUsage(provider="nemotron", model=self.config.model, capability=capability,
            input_tokens=response.input_tokens, output_tokens=response.output_tokens,
            latency_ms=max(response.latency_ms,(perf_counter()-started)*1000), started_at=started_at, completed_at=utc_now())
        return ProviderResult(request_id=usage.request_id, provider="nemotron", model=self.config.model, output=output, usage=usage)

    def safe_health(self) -> ProviderHealth:
        return ProviderHealth(name="nemotron", enabled=self.config.enabled, status="available" if self.config.live_ready else "not_ready",
            capabilities=sorted(SUPPORTED_NEMOTRON_CAPABILITIES,key=lambda value:value.value), configured=self.config.configured,
            live_requests_allowed=self.config.allow_live_requests, model=self.config.model, request_count=self._requests,
            success_count=self._successes, failure_count=self._failures)

    def record_fallback(self, safe_error_code: str | None = None, diagnostic: dict[str, object] | None = None) -> None:
        del safe_error_code, diagnostic
