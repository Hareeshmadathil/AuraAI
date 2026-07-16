from knowledge_manager.cli import main
def test_demo_query_and_safe_context(capsys):
    assert main(["--demo"])==0 and "synthetic=true" in capsys.readouterr().out
    assert main(["--query"])==0 and "matches=" in capsys.readouterr().out
    assert main(["--prepare-content-context"])==0
    assert "mission_executed=false" in capsys.readouterr().out
