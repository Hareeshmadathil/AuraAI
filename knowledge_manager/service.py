"""Offline Knowledge Manager orchestration."""
from knowledge_manager.conflicts import detect_conflict
from knowledge_manager.freshness import refresh_item
from knowledge_manager.ingestion import ingest
from knowledge_manager.models import *
from knowledge_manager.retrieval import retrieve
class KnowledgeManagerService:
    def __init__(self,repository): self.repository=repository; self.conflicts=[]
    def ingest(self,request):
        existing=self.repository.get_item(request.proposed_version.knowledge_id); prior=self.repository.get_version(existing.current_version_id) if existing else None
        result=ingest(self.repository,request)
        if result.accepted and prior:
            conflict=detect_conflict(prior,request.proposed_version)
            if conflict:self.conflicts.append(conflict)
        return result
    def query(self,query): return retrieve(self.repository,query,self.conflicts)
    def refresh_queue(self): return [item for v in self.repository.list_versions() if (item:=refresh_item(v)) is not None]
    def content_context(self,query):
        result=self.query(query); facts=[]; qualified=[]; warnings=[]; unresolved=[]; prohibited=[]; sources=[]; confidences=[]; expiries=[]
        for match in result.matches:
            claims=[x.text for x in match.version.claims]; sources.extend(x.locator for x in match.version.sources); confidences.extend(x.confidence for x in match.version.claims); expiries.append(match.version.freshness.expires_at); warnings.extend(match.freshness_warnings)
            if match.allowed_usage=="approved factual support":facts.extend(claims)
            elif match.conflicts: unresolved.extend(claims); prohibited.extend(claims)
            else:qualified.extend(claims)
        return KnowledgeContextPackage(current_verified_facts=facts,qualified_facts=qualified,freshness_warnings=warnings,unresolved_claims=unresolved,prohibited_claims=prohibited,source_references=sorted(set(sources)),evidence_visuals=[],confidence=sum(confidences)/len(confidences) if confidences else 0,expiry_deadline=min(expiries) if expiries else None,founder_review_status=ApprovalStatus.PENDING if unresolved or warnings else ApprovalStatus.APPROVED,mission_executed=False,rendered=False,published=False)
    def result(self,query=None):
        items=self.repository.list_items(); versions=self.repository.list_versions(); retrieval=self.query(query) if query else None
        return KnowledgeManagerResult(run=KnowledgeManagerRun(synthetic=True),item_count=len(items),current_versions=len(items),historical_versions=max(0,len(versions)-len(items)),conflicts=list(self.conflicts),refresh_queue=self.refresh_queue(),retrieval=retrieval,context=self.content_context(query) if query else None)
