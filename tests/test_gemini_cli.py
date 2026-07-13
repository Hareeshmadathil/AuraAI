"""Safe Gemini CLI tests; every live-shaped call uses a mock transport."""

from providers.gemini.provider import main
from providers.gemini.config import FOUNDER_SMOKE_TEST_TIMEOUT_SECONDS
from providers.gemini import GeminiTransportResponse
from providers.gemini.transport import MockGeminiTransport
from tests.gemini_helpers import response_for


def test_cli_dry_run_performs_no_network(capsys) -> None:
    assert main(["--smoke-test"]) == 0
    output = capsys.readouterr().out
    assert "model=deterministic" in output
    assert "fallback=true" in output


def test_cli_requires_both_live_approval_flags(capsys) -> None:
    assert main(["--smoke-test", "--enable-live"]) == 2
    assert "requires --enable-live and --founder-approved" in capsys.readouterr().out


def test_cli_does_not_accept_visible_api_key_argument() -> None:
    try:
        main(["--smoke-test", "--api-key", "visible-secret"])
    except SystemExit as error:
        assert error.code != 0
    else:
        raise AssertionError("Visible --api-key argument must be rejected.")


def test_cli_mocked_live_success_is_redacted(capsys) -> None:
    secret = "fake-cli-secret"
    transport = MockGeminiTransport(lambda request: response_for(request))
    result = main(
        ["--smoke-test", "--enable-live", "--founder-approved"],
        transport=transport,
        secret_reader=lambda _: secret,
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "success=true" in output
    assert "typed_response=ResearchOutput" in output
    assert secret not in output
    assert transport.timeout_seconds == [FOUNDER_SMOKE_TEST_TIMEOUT_SECONDS]


def test_cli_mocked_live_failure_falls_back_and_is_redacted(capsys) -> None:
    secret = "fake-cli-failure-secret"

    def fail(_request):
        raise RuntimeError(f"must not print {secret}")

    result = main(
        ["--smoke-test", "--enable-live", "--founder-approved"],
        transport=MockGeminiTransport(fail),
        secret_reader=lambda _: secret,
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "success=true" in output
    assert "fallback=true" in output
    assert secret not in output


def test_cli_reports_only_safe_validation_diagnostics(capsys) -> None:
    secret = "fake-cli-diagnostic-secret"

    def reject(request):
        return GeminiTransportResponse(
            request_id=request.request_id,
            status_code=400,
            response_body='{"error":{"message":"raw private response"}}',
            latency_ms=1,
        )

    result = main(
        ["--smoke-test", "--enable-live", "--founder-approved"],
        transport=MockGeminiTransport(reject),
        secret_reader=lambda _: secret,
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "safe_error_code=invalid_request" in output
    assert "validation_stage=http_status" in output
    assert "http_status=400" in output
    assert "parser_stage=http_status" in output
    assert "transport_completed=true" in output
    assert "candidates_found=unknown" in output
    assert "schema_validation_started=false" in output
    assert secret not in output
    assert "raw private response" not in output


def test_cli_prints_transport_classification_without_raw_error(capsys) -> None:
    def reject(request):
        return GeminiTransportResponse(
            request_id=request.request_id,
            status_code=400,
            response_body="",
            latency_ms=1,
            safe_error_code="unsupported_generation_parameter",
        )

    result = main(
        ["--smoke-test", "--enable-live", "--founder-approved"],
        transport=MockGeminiTransport(reject),
        secret_reader=lambda _: "fake-classified-cli-key",
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "safe_error_code=unsupported_generation_parameter" in output
    assert "http_status=400" in output
