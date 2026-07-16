from datetime import datetime
import pytest
from pydantic import ValidationError
from knowledge_manager.fixtures import fixture_requests
from knowledge_manager.models import KnowledgeSourceReference
def test_models_are_strict_aware_and_hash_bearing():
    version=fixture_requests()[0].proposed_version
    assert len(version.content_hash)==64
    with pytest.raises(ValidationError): KnowledgeSourceReference.model_validate({**version.sources[0].model_dump(),"observed_at":datetime.now()})
    with pytest.raises(ValidationError): version.__class__.model_validate({**version.model_dump(),"unknown":True})
def test_updated_version_requires_parent():
    version=fixture_requests()[0].proposed_version
    value=version.model_dump(exclude={"content_hash","version_id"})
    value.update(version=2,parent_version_id=None)
    with pytest.raises(ValidationError): version.__class__(**value)
