import pytest
from knowledge_manager.exceptions import KnowledgeManagerError
from knowledge_manager.fixtures import fixture_requests
from knowledge_manager.repository import InMemoryKnowledgeRepository
from knowledge_manager.service import KnowledgeManagerService
def test_fixture_ingestion_rejects_private_data_and_accepts_provenance():
    requests=fixture_requests();service=KnowledgeManagerService(InMemoryKnowledgeRepository())
    assert service.ingest(requests[0]).accepted
    with pytest.raises(KnowledgeManagerError) as exc:service.ingest(requests[9])
    assert exc.value.code=="PRIVATE_DATA_PROHIBITED"
def test_duplicate_is_detected_without_history_rewrite():
    request=fixture_requests()[0];service=KnowledgeManagerService(InMemoryKnowledgeRepository());service.ingest(request)
    result=service.ingest(request)
    assert not result.accepted and len(service.repository.list_versions())==1
def test_credential_shaped_content_is_rejected():
    request=fixture_requests()[1];version=request.proposed_version.model_copy(update={"summary":"API_KEY=forbidden"});request=request.model_copy(update={"proposed_version":version})
    with pytest.raises(KnowledgeManagerError):KnowledgeManagerService(InMemoryKnowledgeRepository()).ingest(request)
