"""Hash and semantic-key deduplication without embeddings."""
from knowledge_manager.enums import DuplicateKind
from knowledge_manager.models import KnowledgeVersion
def classify_duplicate(proposed:KnowledgeVersion,existing:list[KnowledgeVersion])->tuple[DuplicateKind,KnowledgeVersion|None]:
    for item in existing:
        if proposed.content_hash==item.content_hash:return DuplicateKind.EXACT,item
        claims={x.canonical_text for x in item.claims}; new={x.canonical_text for x in proposed.claims}
        if claims==new and proposed.topic.normalized_name==item.topic.normalized_name:return DuplicateKind.EQUIVALENT,item
        if claims & new:return DuplicateKind.PARTIAL,item
        if proposed.topic.normalized_name==item.topic.normalized_name:return DuplicateKind.VERSION,item
    return DuplicateKind.UNRELATED,None
