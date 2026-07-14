"""Network-free CLI behavior tests."""

from pathlib import Path

from company_missions.first_real_content.cli import build_parser, main


EXAMPLE = Path("founder_inputs/first_content_mission.example.json")


def test_dry_run_is_safe_and_does_not_export(tmp_path: Path, capsys) -> None:
    code = main(["--input", str(EXAMPLE), "--output-root", str(tmp_path), "--dry-run"])
    output = capsys.readouterr().out
    assert code == 0
    assert "mode=deterministic" in output
    assert "api_key" not in output.lower()
    assert not list(tmp_path.iterdir())


def test_cli_has_no_visible_api_key_argument() -> None:
    help_text = build_parser().format_help().lower()
    assert "--api-key" not in help_text


def test_live_flags_must_be_paired(capsys) -> None:
    code = main(["--input", str(EXAMPLE), "--execute", "--enable-live-gemini"])
    assert code == 2
    assert "LIVE_AI_FLAGS_REQUIRED" in capsys.readouterr().out


def test_deterministic_execute_exports_review_package(
    tmp_path: Path, capsys
) -> None:
    code = main(
        [
            "--input",
            str(EXAMPLE),
            "--output-root",
            str(tmp_path),
            "--execute",
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "founder_review_required=true" in output
    assert "rendered=false" in output
    assert "published=false" in output
    assert len(list(tmp_path.glob("*/manifest/artifact-manifest.json"))) == 1
