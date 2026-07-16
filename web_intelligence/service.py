"""Founder-gated orchestration for plans, evidence, and citations."""
from __future__ import annotations
from urllib.parse import urlparse
from agents.specialists.trend_hunter import TrendHunter
from web_intelligence.adapters.base import WebAdapter
from web_intelligence.approvals import ApprovalService
from web_intelligence.citations import citation_for
from web_intelligence.enums import AdapterKind,EvidenceClassification,OperatingMode
from web_intelligence.evidence import create_evidence
from web_intelligence.models import AdapterRequest,Citation,CrawlLimits,DashboardState,EvidenceItem,PlanApproval,WebResearchPlan
from web_intelligence.policy import PROHIBITED_ACTIONS,WebPolicy
from web_intelligence.rate_limits import DomainRateLimiter
from web_intelligence.robots import RobotsPolicy
from web_intelligence.url_safety import UrlSafetyValidator
from runtime_engine.models import RuntimeEventType

class WebIntelligenceService:
    def __init__(self,*,policy:WebPolicy,adapters:dict[AdapterKind,WebAdapter],robots:RobotsPolicy|None=None,rate_limiter:DomainRateLimiter|None=None,event_bus=None):
        self.policy=policy; self.adapters=adapters; self.robots=robots or RobotsPolicy(); self.rate_limiter=rate_limiter or DomainRateLimiter()
        self.approvals=ApprovalService(); self.plans:list[WebResearchPlan]=[]; self.evidence:list[EvidenceItem]=[]; self.citations:list[Citation]=[]; self.blocked_actions:list[str]=[]
        self.event_bus=event_bus
    def draft_plan(self,*,objective:str,question:str,domains:list[str],expected_sources:list[str]|None=None,limits:CrawlLimits|None=None)->WebResearchPlan:
        plan=WebResearchPlan(objective=objective,research_question=question,approved_domains=domains,
            expected_official_sources=expected_sources or [],adapter_rationale="Prefer Crawl4AI/public HTTP; Browser Use only for founder-approved read-only gaps.",
            expected_evidence=["Official public evidence with bounded excerpts."],prohibited_actions=list(PROHIBITED_ACTIONS),limits=limits or CrawlLimits())
        plan=self.approvals.prepare(plan); self.plans.append(plan)
        self._emit(RuntimeEventType.WEB_RESEARCH_PLAN_CREATED,{"plan_id":str(plan.plan_id),"domain_count":len(plan.approved_domains),"status":"pending"})
        return plan
    def approve_plan(self,plan:WebResearchPlan,*,founder_confirmed:bool):
        approved,record=self.approvals.approve(plan,founder_confirmed=founder_confirmed)
        self._emit(RuntimeEventType.WEB_RESEARCH_PLAN_APPROVED,{"plan_id":str(plan.plan_id),"domain_count":len(plan.approved_domains),"status":"approved"})
        return approved,record
    def draft_from_trend_hunter(self,trend_hunter:TrendHunter,*,question:str,domains:list[str])->WebResearchPlan:
        if trend_hunter.identity.job_title!="Trend Hunter": raise ValueError("Existing Trend Hunter role is required.")
        return self.draft_plan(objective="Collect public evidence for a Trend Hunter proposal.",question=question,domains=domains)
    def execute(self,plan:WebResearchPlan,approval:PlanApproval,*,url:str,adapter_kind:AdapterKind,founder_confirmed:bool)->EvidenceItem:
        self.policy.require_execution_mode(); self.approvals.require(plan,approval)
        if not founder_confirmed: raise ValueError("Founder-confirmed execution flag is required.")
        validator=UrlSafetyValidator(plan.approved_domains); canonical=validator.validate(url); self.robots.require_allowed(canonical)
        domain=(urlparse(canonical).hostname or ""); self.rate_limiter.acquire(domain)
        result=self.adapters[adapter_kind].execute(AdapterRequest(plan_id=plan.plan_id,plan_hash=plan.plan_hash,url=canonical,mode=self.policy.mode,founder_confirmed=True))
        item=create_evidence(url=canonical,canonical_url=result.canonical_url,title=result.title,excerpt=result.excerpt,
            summary="Bounded public-source extraction requiring verification.",method=result.adapter,
            classification=EvidenceClassification.PUBLIC_PRIMARY,confidence=.7,robots_allowed=True,freshness="unknown")
        self.evidence.append(item); self.citations.append(citation_for(item)); return item
    def _emit(self,event_type:RuntimeEventType,metadata:dict[str,object])->None:
        if self.event_bus is not None: self.event_bus.emit(event_type,"Web intelligence state changed.",metadata=metadata)
    def dashboard_state(self)->DashboardState:
        domains=sorted({domain for plan in self.plans if plan.founder_approval_status.value=="approved" for domain in plan.approved_domains})
        return DashboardState(mode=self.policy.mode,adapters=[value.status for value in self.adapters.values()],
            pending_plans=sum(plan.founder_approval_status.value=="pending" for plan in self.plans),approved_domains=domains,
            limits=self.policy.limits,evidence_count=len(self.evidence),citation_count=len(self.citations),
            blocked_actions=[*PROHIBITED_ACTIONS,*self.blocked_actions],risk_alerts=["Browser adapters are optional and disabled by default."])
