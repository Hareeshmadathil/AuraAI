"""Storage eligibility and bounded retention policy."""
from knowledge_manager.enums import ConflictStatus,KnowledgeCategory,RetentionAction
from knowledge_manager.models import KnowledgeRetentionDecision,KnowledgeVersion
def decide(version:KnowledgeVersion,*,private_data:bool=False,copyright_risk:bool=False)->KnowledgeRetentionDecision:
    if private_data or version.category==KnowledgeCategory.PRIVATE: action=RetentionAction.PROHIBITED
    elif copyright_risk: action=RetentionAction.DISCARD
    elif version.conflict_status in {ConflictStatus.MATERIAL,ConflictStatus.UNRESOLVED}: action=RetentionAction.FOUNDER
    elif version.approval_status.value=="approved": action=RetentionAction.VERIFIED
    else: action=RetentionAction.TEMPORARY
    return KnowledgeRetentionDecision(knowledge_id=version.knowledge_id,action=action,rationale=["Evidence, privacy, expiry, conflict, and founder status evaluated"])
