"""Explainable deterministic retrieval ranking."""
from knowledge_manager.enums import ApprovalStatus,ConflictStatus,FreshnessStatus
from knowledge_manager.models import KnowledgeQuery,KnowledgeVersion
def score(query:KnowledgeQuery,version:KnowledgeVersion,current:bool)->tuple[float,dict[str,float]]:
    text=query.text.casefold(); topic=35 if text==version.topic.normalized_name else 20 if text in version.topic.normalized_name or version.topic.normalized_name in text else 0
    entity=20*min(1,len({x.casefold() for x in query.entities}&{x.normalized_name for x in version.entities}))
    freshness=15 if version.freshness.status==FreshnessStatus.FRESH else -20 if version.freshness.status in {FreshnessStatus.EXPIRED,FreshnessStatus.STALE} else 0
    authority=sum(x.authority_score for x in version.sources)/max(1,len(version.sources))*.15; confidence=max(x.confidence for x in version.claims)*10; approval=10 if version.approval_status==ApprovalStatus.APPROVED else 0; current_score=10 if current else 0; conflict=-30 if version.conflict_status in {ConflictStatus.MATERIAL,ConflictStatus.UNRESOLVED} else 0
    parts={"topic":topic,"entity":entity,"freshness":freshness,"authority":round(authority,2),"confidence":round(confidence,2),"approval":approval,"current":current_score,"conflict":conflict}; return max(0,min(100,round(sum(parts.values()),2))),parts
