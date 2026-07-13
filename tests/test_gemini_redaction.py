"""Best-effort redaction tests for safe diagnostics."""

from providers.gemini.redaction import redact_sensitive_text


def test_redacts_common_sensitive_formats() -> None:
    value = (
        "Authorization: Bearer fake-token email user@example.com "
        "path C:\\Users\\Person\\secret.txt key=fake-query-key"
    )
    redacted = redact_sensitive_text(value, ("fake-token",))
    assert "fake-token" not in redacted
    assert "user@example.com" not in redacted
    assert "C:\\Users\\Person" not in redacted
    assert "fake-query-key" not in redacted
    assert "[REDACTED" in redacted


def test_redaction_is_documented_as_best_effort_not_persistence() -> None:
    assert redact_sensitive_text("ordinary safe summary") == "ordinary safe summary"
