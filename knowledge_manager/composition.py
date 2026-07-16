"""Zero-argument in-memory demo composition."""
from functools import lru_cache
from knowledge_manager.fixtures import fixture_requests
from knowledge_manager.repository import InMemoryKnowledgeRepository
from knowledge_manager.service import KnowledgeManagerService
from knowledge_manager.models import KnowledgeQuery
@lru_cache(maxsize=1)
def create_demo_service():
    service=KnowledgeManagerService(InMemoryKnowledgeRepository())
    for request in fixture_requests():
        try: service.ingest(request)
        except Exception: pass
    return service
def create_demo_result(): return create_demo_service().result(KnowledgeQuery(text="gemini structured json"))
