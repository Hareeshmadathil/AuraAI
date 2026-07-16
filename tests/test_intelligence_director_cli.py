from intelligence_director.cli import main
def test_cli_demo_and_safe_handoffs(capsys):
    assert main(["--demo"])==0
    assert "synthetic=true" in capsys.readouterr().out
    assert main(["--prepare-web-plan"])==0
    output=capsys.readouterr().out
    assert "live_execution=false" in output and "founder_approval=true" in output
