from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_intelligence_director_demo_app
from intelligence_director.composition import create_demo_result
from intelligence_director.exporter import IntelligenceExporter

def test_demo_is_deterministic_safe_and_founder_gated():
    first=create_demo_result(); second=create_demo_result()
    assert [x.overall for x in first.priorities]==[x.overall for x in second.priorities]
    assert not first.queue.execution_enabled and first.web_plan_request.live_execution is False
    assert not first.mission_executed and not first.rendered and not first.published
def test_export_tree_is_atomic_and_csv_safe(tmp_path:Path):
    root=IntelligenceExporter(tmp_path).export(create_demo_result())
    expected=["run/run-summary.json","queue/research-queue.json","queue/queue-summary.csv","handoff/web-research-plan-request.json","handoff/content-opportunity-context.json"]
    assert all((root/name).is_file() for name in expected)
    assert not list(root.rglob("*.tmp"))
def test_dashboard_route_discloses_boundaries():
    response=TestClient(create_intelligence_director_demo_app()).get("/intelligence-director")
    assert response.status_code==200
    for text in ("OFFLINE","FOUNDER APPROVAL REQUIRED","NO LIVE RESEARCH","NOT RENDERED","NOT PUBLISHED","Research queue","Contradictions"):
        assert text in response.text
