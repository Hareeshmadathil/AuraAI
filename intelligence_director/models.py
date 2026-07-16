"""Strict typed artifacts for offline intelligence prioritization."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timedelta
from typing import Any
from uuid import UUID,uuid4
from pydantic import Field,field_validator,model_validator
from core import AuraBaseModel,utc_now
from intelligence_director.enums import *

def content_hash(value:Any)->str:
    if hasattr(value,"model_dump"): value=value.model_dump(mode="json",exclude={"content_hash"})
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def _aware(value:datetime|None)->datetime|None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None): raise ValueError("Timestamp must be timezone-aware.")
    return value
class SignalContext(AuraBaseModel):
    business_relevance:float=Field(ge=0,le=100); audience_relevance:float=Field(ge=0,le=100); urgency:float=Field(ge=0,le=100); content_opportunity_id:UUID|None=None
class IntelligenceSignal(AuraBaseModel):
    signal_id:UUID=Field(default_factory=uuid4); source:SignalSource; source_name:str=Field(min_length=1,max_length=100); topic:str=Field(min_length=1,max_length=300); summary:str=Field(min_length=1,max_length=2000); entities:list[str]=Field(default_factory=list,max_length=30); evidence_references:list[str]=Field(default_factory=list,max_length=30); observed_at:datetime=Field(default_factory=utc_now); freshness_window_hours:int=Field(ge=1,le=8760); context:SignalContext; confidence:float=Field(ge=0,le=1); verification_status:VerificationStatus; synthetic:bool=False; content_hash:str=Field(default="",pattern=r"^(?:|[a-f0-9]{64})$")
    @field_validator("observed_at")
    @classmethod
    def aware(cls,v): return _aware(v)
    @model_validator(mode="after")
    def hashed(self):
        expected=content_hash(self)
        if self.content_hash and self.content_hash!=expected: raise ValueError("Signal content hash mismatch.")
        object.__setattr__(self,"content_hash",expected); return self
class ResearchQuestion(AuraBaseModel): question_id:UUID=Field(default_factory=uuid4); text:str=Field(min_length=1,max_length=1000)
class ResearchObjective(AuraBaseModel): objective_id:UUID=Field(default_factory=uuid4); description:str=Field(min_length=1,max_length=1000); success_evidence:list[str]=Field(default_factory=list,max_length=20)
class ResearchCandidate(AuraBaseModel): candidate_id:UUID=Field(default_factory=uuid4); signal_ids:list[UUID]=Field(min_length=1); question:ResearchQuestion; objective:ResearchObjective; duplicate_topic:bool=False; verification_cost:float=Field(default=30,ge=0,le=100)
class ResearchPriorityScore(AuraBaseModel):
    candidate_id:UUID; dimensions:dict[str,float]; weighted_contributions:dict[str,float]; overall:float=Field(ge=0,le=100); band:PriorityBand; rationale:list[str]; heuristic_only:bool=True; no_performance_guarantee:bool=True
class ResearchDepthRecommendation(AuraBaseModel):
    depth:ResearchDepth; rationale:list[str]; expected_sources:list[str]; maximum_pages:int=Field(ge=0,le=5); maximum_duration_seconds:int=Field(ge=0,le=60); required_official_sources:int=Field(ge=0,le=3); competitor_sources_allowed:bool=False; contradiction_checks:list[str]; freshness_deadline:datetime; stop_conditions:list[str]; expected_evidence:list[str]; founder_approval_required:bool=True
    _time=field_validator("freshness_deadline")(_aware)
class SourceAuthorityAssessment(AuraBaseModel):
    source_reference:str; category:str; authority_score:float=Field(ge=0,le=100); confidence:float=Field(ge=0,le=1); reasons:list[str]; limitations:list[str]; required_verification:list[str]; allowed_usage:AuthorityUse; region_mismatch:bool=False; stale:bool=False
class EvidenceWeight(AuraBaseModel):
    claim:str=Field(max_length=1000); supporting_evidence:list[str]; opposing_evidence:list[str]; total_support_weight:float=Field(ge=0,le=100); total_opposition_weight:float=Field(ge=0,le=100); confidence:float=Field(ge=0,le=1); verification_status:VerificationStatus; allowed_wording:list[str]; prohibited_wording:list[str]; further_research_required:bool
class EvidenceConflict(AuraBaseModel): claim_a:str; claim_b:str; source_references:list[str]
class ContradictionGroup(AuraBaseModel):
    group_id:UUID=Field(default_factory=uuid4); status:ContradictionStatus; summary:str; affected_claims:list[str]; source_references:list[str]; recommended_wording:str; founder_verification_checklist:list[str]; blocks_content_production:bool
class FreshnessPolicy(AuraBaseModel): category:str; refresh_hours:int=Field(ge=1,le=87600); expiry_hours:int=Field(ge=1,le=87600); timeless:bool=False
class FreshnessAssessment(AuraBaseModel):
    item_id:UUID; observed_at:datetime; valid_from:datetime; last_verified_at:datetime|None=None; refresh_after:datetime; expires_at:datetime; status:FreshnessStatus; replacement_version:UUID|None=None; archive_reason:str|None=None
    _times=field_validator("observed_at","valid_from","last_verified_at","refresh_after","expires_at")(_aware)
class KnowledgeRetentionDecision(AuraBaseModel): item_id:UUID; action:RetentionAction; rationale:list[str]; expires_at:datetime|None=None; founder_review_required:bool
class CompetitorResearchCandidate(AuraBaseModel): competitor_id:UUID=Field(default_factory=uuid4); name:str; approved_public_domains:list[str]; permitted_questions:list[str]; prohibited_collection:list[str]=Field(default_factory=lambda:["private analytics","follower lists","creative copying"]); audience_overlap:float=Field(ge=0,le=100); topic_overlap:float=Field(ge=0,le=100); strategic_relevance:float=Field(ge=0,le=100); research_cost:float=Field(ge=0,le=100); verified_evidence_only:bool=True
class CompetitorPriorityScore(AuraBaseModel): competitor_id:UUID; score:float=Field(ge=0,le=100); rationale:list[str]; approved_public_domains:list[str]; evidence_required:list[str]; refresh_cadence_days:int=Field(ge=1)
class ResearchQueueItem(AuraBaseModel):
    queue_item_id:UUID=Field(default_factory=uuid4); order:int=Field(ge=1); research_question:ResearchQuestion; priority_score:ResearchPriorityScore; assigned_system:str; recommended_depth:ResearchDepthRecommendation; approved_domains:list[str]; expected_evidence:list[str]; expires_at:datetime; blocking_dependencies:list[UUID]=Field(default_factory=list); founder_approval_status:FounderDecision=FounderDecision.PENDING; execution_status:QueueStatus=QueueStatus.AWAITING; content_hash:str=Field(default="",pattern=r"^(?:|[a-f0-9]{64})$"); parent_item_id:UUID|None=None
    @model_validator(mode="after")
    def no_execution(self):
        object.__setattr__(self,"content_hash",content_hash(self)); return self
class ResearchQueue(AuraBaseModel): queue_id:UUID=Field(default_factory=uuid4); version:int=Field(default=1,ge=1); parent_queue_id:UUID|None=None; items:list[ResearchQueueItem]; created_at:datetime=Field(default_factory=utc_now); founder_approval_status:FounderDecision=FounderDecision.PENDING; execution_enabled:bool=False
class IntelligenceRecommendation(AuraBaseModel): recommendation_id:UUID=Field(default_factory=uuid4); action:str; rationale:list[str]; confidence:float=Field(ge=0,le=1); founder_review_required:bool=True
class FounderIntelligenceDecision(AuraBaseModel): decision_id:UUID=Field(default_factory=uuid4); item_id:UUID; decision:FounderDecision; decided_at:datetime|None=None; exact_content_hash:str=Field(pattern=r"^[a-f0-9]{64}$")
class WebResearchPlanRequest(AuraBaseModel):
    request_id:UUID=Field(default_factory=uuid4); objective:str; research_question:str; priority:float=Field(ge=0,le=100); research_depth:ResearchDepth; approved_domains:list[str]; official_sources_expected:list[str]; maximum_pages:int=Field(ge=0,le=5); maximum_duration_seconds:int=Field(ge=0,le=60); expected_evidence:list[str]; prohibited_actions:list[str]; freshness_deadline:datetime; founder_approval_required:bool=True; live_execution:bool=False; plan_hash:str=Field(default="",pattern=r"^(?:|[a-f0-9]{64})$")
    @model_validator(mode="after")
    def safe(self):
        if self.live_execution: raise ValueError("Intelligence Director cannot execute Web Intelligence.")
        object.__setattr__(self,"plan_hash",content_hash(self)); return self
class ContentOpportunityContext(AuraBaseModel):
    context_id:UUID=Field(default_factory=uuid4); topic:str; verified_facts:list[str]; unresolved_claims:list[str]; prohibited_claims:list[str]; freshness_deadline:datetime; audience:str; business_objective:str; likely_platform:str; content_gap:str; evidence_visuals:list[str]; monetization_hypothesis:str; research_completeness:float=Field(ge=0,le=1); founder_review_status:FounderDecision=FounderDecision.PENDING; mission_executed:bool=False; published:bool=False
class IntelligenceRun(AuraBaseModel): run_id:UUID=Field(default_factory=uuid4); version:int=1; parent_run_id:UUID|None=None; started_at:datetime=Field(default_factory=utc_now); offline:bool=True; deterministic:bool=True; signal_ids:list[UUID]
class IntelligenceResult(AuraBaseModel):
    run:IntelligenceRun; signals:list[IntelligenceSignal]; authority_assessments:list[SourceAuthorityAssessment]; evidence_weights:list[EvidenceWeight]; priorities:list[ResearchPriorityScore]; competitor_priorities:list[CompetitorPriorityScore]; contradictions:list[ContradictionGroup]; freshness:list[FreshnessAssessment]; retention_decisions:list[KnowledgeRetentionDecision]; recommendations:list[IntelligenceRecommendation]; queue:ResearchQueue; web_plan_request:WebResearchPlanRequest|None; content_context:ContentOpportunityContext|None; completed_at:datetime=Field(default_factory=utc_now); live_research_performed:bool=False; mission_executed:bool=False; rendered:bool=False; published:bool=False
