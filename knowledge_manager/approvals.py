"""Exact hash-bound founder approval validation."""
from core import utc_now
from knowledge_manager.enums import FounderDecision
from knowledge_manager.exceptions import KnowledgeManagerError
from knowledge_manager.models import KnowledgeApproval,KnowledgeVersion,hash_value
def evidence_hash(version:KnowledgeVersion)->str: return hash_value([x.model_dump(mode="json") for x in version.evidence_links])
def require_store_approval(version:KnowledgeVersion,approval:KnowledgeApproval|None)->None:
    if approval is None: raise KnowledgeManagerError("Exact founder approval is required.",code="APPROVAL_REQUIRED")
    if approval.decision not in {FounderDecision.APPROVE,FounderDecision.SIGNAL}: raise KnowledgeManagerError("Founder decision does not permit storage.",code="APPROVAL_REJECTED")
    if approval.version_id!=version.version_id or approval.content_hash!=version.content_hash or approval.evidence_hash!=evidence_hash(version) or approval.retention_action!=version.retention_policy.action: raise KnowledgeManagerError("Approval is not bound to this exact version.",code="APPROVAL_MISMATCH")
    if approval.expires_at<=utc_now(): raise KnowledgeManagerError("Founder approval expired.",code="APPROVAL_EXPIRED")
