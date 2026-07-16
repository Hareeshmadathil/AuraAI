"""Stable local lookup keys."""
from knowledge_manager.models import KnowledgeVersion
def index_keys(version:KnowledgeVersion)->set[str]:
    return {version.topic.normalized_name,version.category.value,*(x.normalized_name for x in version.entities),*(x.canonical_text for x in version.claims)}
