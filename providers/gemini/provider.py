"""Transport-injected, explicitly enabled Gemini capability adapter."""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from time import sleep

from core import AuraAIError, utc_now
from providers.exceptions import ProviderRateLimitError, ProviderUnavailableError
from providers.gemini.config import GeminiConfig
from providers.gemini.models import (
    GeminiParserStage,
    GeminiRequest,
    GeminiSafeDiagnostic,
    GeminiValidatedResponse,
    GeminiValidationStage,
)
from providers.gemini.prompt_builder import GeminiPromptBuilder
from providers.gemini.response_parser import GeminiResponseParser
from providers.gemini.transport import (
    GeminiTransport,
    HttpGeminiTransport,
    UnavailableGeminiTransport,
)
from providers.models import (
    ProviderCapability,
    ProviderDescriptor,
    ProviderHealth,
    ProviderKind,
    ProviderOutput,
)
from providers.prompt_template import (
    PromptCategory,
    ProviderPrompt,
    build_department_prompt,
)
from providers.provider_result import ProviderResult


SUPPORTED_GEMINI_CAPABILITIES = frozenset(
    {
        ProviderCapability.RESEARCH,
        ProviderCapability.SCRIPT,
        ProviderCapability.HOOK,
        ProviderCapability.STORY,
        ProviderCapability.SEO,
        ProviderCapability.MARKETING,
        ProviderCapability.REVIEW,
        ProviderCapability.METADATA,
        ProviderCapability.AUDIENCE,
    }
)


class GeminiProvider:
    """Produce neutral typed advice through an injected Gemini transport."""

    def __init__(
        self,
        config: GeminiConfig | None = None,
        transport: GeminiTransport | None = None,
        *,
        prompt_builder: GeminiPromptBuilder | None = None,
        response_parser: GeminiResponseParser | None = None,
        sleep_function: Callable[[float], None] = sleep,
    ) -> None:
        self.config = config or GeminiConfig()
        self.transport = transport or UnavailableGeminiTransport()
        self.prompt_builder = prompt_builder or GeminiPromptBuilder()
        self.response_parser = response_parser or GeminiResponseParser()
        self._sleep = sleep_function
        self.descriptor = ProviderDescriptor(
            name="gemini",
            kind=ProviderKind.REMOTE,
            enabled=self.config.enabled,
            model=self.config.model,
            capabilities=SUPPORTED_GEMINI_CAPABILITIES,
        )
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._fallback_count = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_latency_ms = 0.0
        self._last_safe_error_code: str | None = None
        self._last_safe_diagnostic: GeminiSafeDiagnostic | None = None
        self._last_request_at: datetime | None = None
        self._daily_counts: dict[date, int] = {}

    def check_ready(self) -> None:
        """Fail safely unless every live-request gate is explicit."""

        if not self.config.enabled:
            raise ProviderUnavailableError(
                "Gemini is disabled; deterministic fallback remains active.",
                provider_name="gemini",
                retryable=False,
            )
        if not self.config.allow_live_requests:
            raise ProviderUnavailableError(
                "Gemini live requests were not explicitly allowed.",
                provider_name="gemini",
                retryable=False,
            )
        if not self.config.configured:
            raise ProviderUnavailableError(
                "Gemini requires an explicitly injected API key.",
                provider_name="gemini",
                retryable=False,
            )
        if self.config.request_budget is not None and (
            self._request_count >= self.config.request_budget
        ):
            raise ProviderRateLimitError(
                "Gemini request budget was exhausted.",
                provider_name="gemini",
                retryable=False,
            )
        today = datetime.now(UTC).date()
        if self.config.daily_request_limit is not None and (
            self._daily_counts.get(today, 0) >= self.config.daily_request_limit
        ):
            raise ProviderRateLimitError(
                "Gemini daily request limit was reached.",
                provider_name="gemini",
                retryable=False,
            )

    def generate(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderResult[ProviderOutput]:
        self.check_ready()
        if capability not in SUPPORTED_GEMINI_CAPABILITIES:
            raise ProviderUnavailableError(
                "Gemini does not support this capability in adapter v1.",
                provider_name="gemini",
                retryable=False,
            )
        request = self.prompt_builder.build_request(capability, prompt, self.config)
        self._request_count += 1
        today = datetime.now(UTC).date()
        self._daily_counts[today] = self._daily_counts.get(today, 0) + 1
        self._last_request_at = utc_now()
        try:
            validated = self._execute_with_retries(request, capability)
        except Exception as error:
            self._last_safe_error_code = self._safe_error_code(error)
            self._last_safe_diagnostic = self._diagnostic_from_error(error)
            raise
        self._record_success(validated)
        return ProviderResult[ProviderOutput](
            request_id=validated.request_id,
            provider="gemini",
            model=self.config.model,
            output=validated.typed_payload,
            usage=validated.usage,
            warnings=validated.validation_warnings,
        )

    def record_fallback(
        self,
        safe_error_code: str | None = None,
        diagnostic: dict[str, object] | None = None,
    ) -> None:
        self._failure_count += 1
        self._fallback_count += 1
        self._last_safe_error_code = safe_error_code
        if diagnostic:
            self._last_safe_diagnostic = GeminiSafeDiagnostic.model_validate(
                diagnostic
            )

    def safe_health(self) -> ProviderHealth:
        """Return operational metadata without credentials or content."""

        if not self.config.enabled:
            status = "disabled"
        elif not self.config.live_ready:
            status = "not_ready"
        elif self._last_safe_error_code:
            status = "degraded"
        else:
            status = "available"
        return ProviderHealth(
            name="gemini",
            enabled=self.config.enabled,
            status=status,
            capabilities=sorted(
                SUPPORTED_GEMINI_CAPABILITIES,
                key=lambda value: value.value,
            ),
            configured=self.config.configured,
            live_requests_allowed=self.config.allow_live_requests,
            model=self.config.model,
            request_count=self._request_count,
            success_count=self._success_count,
            failure_count=self._failure_count,
            fallback_count=self._fallback_count,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            average_latency_ms=(
                self._total_latency_ms / self._success_count
                if self._success_count
                else 0
            ),
            last_safe_error_code=self._last_safe_error_code,
            last_request_at=self._last_request_at,
            details=(
                self._last_safe_diagnostic.model_dump(mode="json")
                if self._last_safe_diagnostic is not None
                else {}
            ),
        )

    def _execute_with_retries(
        self,
        request: GeminiRequest,
        capability: ProviderCapability,
    ) -> GeminiValidatedResponse:
        last_error: Exception | None = None
        for attempt in range(self.config.maximum_retries + 1):
            try:
                response = self.transport.send(
                    request,
                    timeout_seconds=self.config.timeout_seconds,
                )
                return self.response_parser.parse_transport_response(
                    response,
                    capability,
                    model=self.config.model,
                    prompt_metadata=request.metadata,
                )
            except Exception as error:
                last_error = error
                retryable = isinstance(error, AuraAIError) and error.retryable
                if not retryable or attempt >= self.config.maximum_retries:
                    raise
                self._sleep(self.config.retry_backoff_seconds * (2**attempt))
        raise ProviderUnavailableError(
            "Gemini execution failed safely.", provider_name="gemini"
        ) from last_error

    def _record_success(self, value: GeminiValidatedResponse) -> None:
        self._success_count += 1
        self._input_tokens += value.usage.input_tokens
        self._output_tokens += value.usage.output_tokens
        self._total_latency_ms += value.usage.latency_ms
        self._last_safe_error_code = None
        self._last_safe_diagnostic = None

    @staticmethod
    def _safe_error_code(error: Exception) -> str:
        if isinstance(error, AuraAIError):
            return str(error.details.get("safe_error_code") or error.error_code)
        return "UNEXPECTED_PROVIDER_ERROR"

    @classmethod
    def _diagnostic_from_error(cls, error: Exception) -> GeminiSafeDiagnostic:
        details = getattr(error, "details", {})
        values = {
            key: details.get(key)
            for key in GeminiSafeDiagnostic.model_fields
            if key in details
        }
        values.setdefault("safe_error_code", cls._safe_error_code(error))
        values.setdefault(
            "validation_stage", GeminiValidationStage.TRANSPORT.value
        )
        values.setdefault("parser_stage", GeminiParserStage.NOT_STARTED.value)
        values.setdefault("transport_completed", False)
        values.setdefault("schema_validation_started", False)
        return GeminiSafeDiagnostic.model_validate(values)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Gemini adapter smoke test")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--founder-approved", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: GeminiTransport | None = None,
    secret_reader: Callable[[str], str] = getpass.getpass,
) -> int:
    """Run a deterministic dry-run or explicitly approved live smoke test."""

    args = _build_cli_parser().parse_args(argv)
    if not args.smoke_test:
        print("No request made. Use --smoke-test for the safe dry-run.")
        return 0
    live = args.enable_live or args.founder_approved
    if live and not (args.enable_live and args.founder_approved):
        print("Live smoke test requires --enable-live and --founder-approved.")
        return 2
    if not live:
        print("capability=research")
        print("model=deterministic")
        print("success=true")
        print("latency_ms=0")
        print("tokens=0/0")
        print("typed_response=ResearchOutput")
        print("fallback=true")
        return 0
    api_key = secret_reader("Gemini API key (input hidden): ").strip()
    if not api_key:
        print("success=false")
        return 2
    config = GeminiConfig(
        enabled=True,
        allow_live_requests=True,
        api_key=api_key,
        request_budget=1,
        maximum_retries=0,
    )
    selected_transport = transport or HttpGeminiTransport(
        base_url=config.base_url,
        api_key=config.api_key_value,
    )
    from providers.composition import create_provider_router

    router = create_provider_router(config, selected_transport)
    prompt = build_department_prompt(
        "gemini_smoke_test",
        PromptCategory.RESEARCH,
        "Give one safe, verifiable content-research principle.",
    )
    try:
        result = router.route(ProviderCapability.RESEARCH, prompt)
    except Exception:
        print("capability=research")
        print(f"model={config.model}")
        print("success=false")
        print("fallback=false")
        return 1
    print("capability=research")
    print(f"model={config.model}")
    print("success=true")
    print(f"latency_ms={result.usage.latency_ms:.2f}")
    print(f"tokens={result.usage.input_tokens}/{result.usage.output_tokens}")
    print(f"typed_response={result.output.__class__.__name__}")
    print(f"fallback={'true' if result.fallback_used else 'false'}")
    if result.fallback_used:
        state = router.build_state()
        health = next(item for item in state.health if item.name == "gemini")
        diagnostic = health.details
        print(f"safe_error_code={health.last_safe_error_code or 'unknown'}")
        print(f"validation_stage={diagnostic.get('validation_stage', 'unknown')}")
        print(f"http_status={diagnostic.get('http_status') or 'none'}")
        print(f"parser_stage={diagnostic.get('parser_stage', 'unknown')}")
        print(
            "transport_completed="
            f"{str(bool(diagnostic.get('transport_completed'))).lower()}"
        )
        candidates = diagnostic.get("candidates_found")
        print(
            "candidates_found="
            f"{str(candidates).lower() if candidates is not None else 'unknown'}"
        )
        print(
            "schema_validation_started="
            f"{str(bool(diagnostic.get('schema_validation_started'))).lower()}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
