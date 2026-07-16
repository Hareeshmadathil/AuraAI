"""CLI and dashboard disclosures with no network calls."""
from fastapi.testclient import TestClient
from app.main import create_web_intelligence_demo_app
from web_intelligence.cli import main
from web_intelligence.composition import create_offline_demo_service

def test_cli_safe_inventory_and_live_failure(capsys):
    assert main(["--list-adapters"])==0; output=capsys.readouterr().out
    assert "adapter=crawl4ai available=" in output
    assert "adapter=browser_use available=false version=0.13.4" in output
    assert main(["--crawl-public"])==2
def test_offline_demo_is_deterministic_and_no_execution():
    first=create_offline_demo_service().dashboard_state(); second=create_offline_demo_service().dashboard_state()
    assert first.model_dump(exclude={"adapters"})==second.model_dump(exclude={"adapters"})
    assert first.mode==OperatingMode.OFFLINE and first.evidence_count==0 and not first.publishing_allowed
def test_dashboard_disclosures():
    response=TestClient(create_web_intelligence_demo_app()).get("/web-intelligence")
    assert response.status_code==200
    for value in ("READ ONLY","NO LOGIN","NO PUBLISHING","robots.txt"):
        assert value in response.text

from web_intelligence.enums import OperatingMode
