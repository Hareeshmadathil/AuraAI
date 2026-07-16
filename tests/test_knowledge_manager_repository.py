from pathlib import Path
import pytest
from knowledge_manager.exceptions import KnowledgeManagerError
from knowledge_manager.fixtures import fixture_requests
from knowledge_manager.models import KnowledgeItem
from knowledge_manager.repository import InMemoryKnowledgeRepository
from knowledge_manager.sqlite_repository import SCHEMA_VERSION,SQLiteKnowledgeRepository
def test_memory_repository_uses_defensive_copies():
    v=fixture_requests()[0].proposed_version;r=InMemoryKnowledgeRepository();r.save_new(KnowledgeItem(knowledge_id=v.knowledge_id,current_version_id=v.version_id),v)
    loaded=r.get_version(v.version_id);object.__setattr__(loaded,"summary","changed")
    assert r.get_version(v.version_id).summary!=loaded.summary
def test_sqlite_schema_transactions_and_parameterized_lookup(tmp_path:Path):
    path=tmp_path/"knowledge.db";r=SQLiteKnowledgeRepository(path,allowed_root=tmp_path);r.initialize();assert r.schema_version()==SCHEMA_VERSION
    v=fixture_requests()[0].proposed_version;r.save_new(KnowledgeItem(knowledge_id=v.knowledge_id,current_version_id=v.version_id),v)
    assert r.get_version(v.version_id).content_hash==v.content_hash
    assert r.list_versions(v.knowledge_id)[0].topic.name==v.topic.name
def test_database_path_escape_is_rejected(tmp_path:Path):
    with pytest.raises(KnowledgeManagerError): SQLiteKnowledgeRepository(tmp_path.parent/"outside.db",allowed_root=tmp_path)
