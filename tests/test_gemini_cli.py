"""Safe Gemini CLI tests; every live-shaped call uses a mock transport."""

from providers.gemini.provider import main
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
