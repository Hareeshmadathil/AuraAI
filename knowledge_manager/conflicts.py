"""Preserve incompatible knowledge versions and block unsafe factual use."""
from intelligence_director.contradiction_detection import detect_contradiction
from intelligence_director.models import EvidenceConflict
from knowledge_manager.enums import ConflictStatus
from knowledge_manager.models import KnowledgeConflict,KnowledgeVersion
MAP={"region_specific":ConflictStatus.REGION,"time_version_conflict":ConflictStatus.VERSION,"material_conflict":ConflictStatus.MATERIAL,"withdrawn_or_corrected":ConflictStatus.CORRECTED}
def detect_conflict(old:KnowledgeVersion,new:KnowledgeVersion)->KnowledgeConflict|None:
    old_claims={x.canonical_text:x for x in old.claims}; new_claims={x.canonical_text:x for x in new.claims}
    if set(old_claims)==set(new_claims):return None
    a=old.claims[0]; b=new.claims[0]; contradiction=detect_contradiction(EvidenceConflict(claim_a=a.text,claim_b=b.text,source_references=[x.locator for x in old.sources+new.sources]))
    status=MAP.get(contradiction.status.value,ConflictStatus.MATERIAL); blocked=status in {ConflictStatus.MATERIAL,ConflictStatus.UNRESOLVED,ConflictStatus.VERSION}
    return KnowledgeConflict(knowledge_id=old.knowledge_id,version_ids=[old.version_id,new.version_id],status=status,affected_claims=[a.text,b.text],evidence_ids=[x.link_id for x in old.evidence_links+new.evidence_links],allowed_wording=[contradiction.recommended_wording],prohibited_wording=["proven","current fact","guaranteed"],factual_use_blocked=blocked)
