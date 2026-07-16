"""Typed retention decisions; no database or vector store."""
from intelligence_director.enums import ContradictionStatus,RetentionAction,VerificationStatus
from intelligence_director.models import KnowledgeRetentionDecision
def decide_retention(item_id,verification:VerificationStatus,contradiction:ContradictionStatus,expires_at,*,private_data:bool=False):
    if private_data: action=RetentionAction.DISCARD
    elif contradiction not in {ContradictionStatus.NONE,ContradictionStatus.RESOLVABLE}: action=RetentionAction.FOUNDER
    elif verification==VerificationStatus.VERIFIED: action=RetentionAction.UNTIL_EXPIRY
    else: action=RetentionAction.TEMPORARY
    return KnowledgeRetentionDecision(item_id=item_id,action=action,rationale=["Bounded typed-artifact retention"],expires_at=expires_at,founder_review_required=action==RetentionAction.FOUNDER)
