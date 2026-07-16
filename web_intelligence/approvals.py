"""Hash-bound founder approval workflow."""
import hashlib,json
from core import utc_now
from web_intelligence.enums import ApprovalState
from web_intelligence.exceptions import ApprovalError
from web_intelligence.models import PlanApproval,WebResearchPlan

def plan_hash(plan:WebResearchPlan)->str:
    payload=plan.model_dump(mode="json",exclude={"plan_hash","founder_approval_status"})
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
class ApprovalService:
    def prepare(self,plan:WebResearchPlan)->WebResearchPlan: return plan.model_copy(update={"plan_hash":plan_hash(plan)})
    def approve(self,plan:WebResearchPlan,*,founder_confirmed:bool)->tuple[WebResearchPlan,PlanApproval]:
        if not founder_confirmed: raise ApprovalError("Explicit founder confirmation is required.",error_code="FOUNDER_CONFIRMATION_REQUIRED")
        expected=plan_hash(plan)
        if plan.plan_hash!=expected: raise ApprovalError("Plan hash mismatch.",error_code="PLAN_HASH_MISMATCH")
        if plan.expires_at<=utc_now(): raise ApprovalError("Research plan expired.",error_code="PLAN_EXPIRED")
        approved=plan.model_copy(update={"founder_approval_status":ApprovalState.APPROVED})
        return approved,PlanApproval(plan_id=plan.plan_id,plan_hash=expected,approved_domains=plan.approved_domains,expires_at=plan.expires_at)
    def require(self,plan:WebResearchPlan,approval:PlanApproval|None)->None:
        if approval is None or approval.state!=ApprovalState.APPROVED: raise ApprovalError("Approved plan is required.",error_code="PLAN_APPROVAL_REQUIRED")
        if approval.plan_id!=plan.plan_id or approval.plan_hash!=plan_hash(plan): raise ApprovalError("Approval is not bound to this plan.",error_code="PLAN_APPROVAL_MISMATCH")
        if approval.expires_at<=utc_now(): raise ApprovalError("Plan approval expired.",error_code="PLAN_EXPIRED")
