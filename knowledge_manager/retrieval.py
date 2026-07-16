"""Filtered local retrieval with freshness/conflict warnings."""
from knowledge_manager.enums import ApprovalStatus,ConflictStatus,FreshnessStatus
from knowledge_manager.models import KnowledgeMatch,KnowledgeQuery,KnowledgeRetrievalResult
from knowledge_manager.relevance import score
def retrieve(repository,query:KnowledgeQuery,conflicts=())->KnowledgeRetrievalResult:
    items={x.knowledge_id:x for x in repository.list_items()}; matches=[]; versions=repository.list_versions()
    for version in versions:
        current=items[version.knowledge_id].current_version_id==version.version_id; f=query.filters
        if f.current_only and not current:continue
        if f.category and version.category!=f.category:continue
        if f.freshness and version.freshness.status!=f.freshness:continue
        if f.founder_approved_only and version.approval_status!=ApprovalStatus.APPROVED:continue
        if max(x.confidence for x in version.claims)<f.minimum_confidence:continue
        relevance,parts=score(query,version,current)
        if relevance<=0:continue
        related=[x for x in conflicts if version.version_id in x.version_ids]; warnings=[]
        if version.freshness.status!=FreshnessStatus.FRESH:warnings.append(f"Freshness: {version.freshness.status.value}")
        blocked=any(x.factual_use_blocked for x in related)
        matches.append(KnowledgeMatch(version=version,relevance_score=relevance,score_explanation=parts,current=current,freshness_warnings=warnings,conflicts=[x.conflict_id for x in related],allowed_usage="research signal only" if blocked or warnings else "approved factual support" if version.approval_status==ApprovalStatus.APPROVED else "qualified context",required_verification=["Founder/current-source verification required"] if blocked or warnings else []))
    matches.sort(key=lambda x:(-x.relevance_score,str(x.version.version_id))); return KnowledgeRetrievalResult(query=query,matches=matches[:query.limit],total_considered=len(versions))
