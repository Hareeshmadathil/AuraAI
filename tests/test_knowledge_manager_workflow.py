from fastapi.testclient import TestClient
from app.main import create_knowledge_manager_demo_app
from knowledge_manager.composition import create_demo_result,create_demo_service
from knowledge_manager.models import KnowledgeQuery
def test_retrieval_has_explanations_and_safe_context():
    service=create_demo_service();result=service.query(KnowledgeQuery(text="gemini structured json"))
    assert result.matches and result.matches[0].score_explanation
    context=service.content_context(KnowledgeQuery(text="gemini structured json"))
    assert not context.mission_executed and not context.rendered and not context.published
def test_refresh_queue_contains_expired_provider_memory():
    assert create_demo_result().refresh_queue
def test_dashboard_route_and_disclosures():
    response=TestClient(create_knowledge_manager_demo_app()).get("/knowledge-manager")
    assert response.status_code==200
    for text in ("OFFLINE","FOUNDER CONTROLLED","NO LIVE RESEARCH","NOT RENDERED","NOT PUBLISHED","Sample retrieval"):
        assert text in response.text
