"""Typed plans, evidence, policies, and adapter results."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID,uuid4
from pydantic import Field, model_validator
from core import AuraBaseModel, utc_now
from web_intelligence.enums import AdapterKind,ApprovalState,EvidenceClassification,OperatingMode

class CrawlLimits(AuraBaseModel):
    concurrent_browsers:int=Field(default=1,ge=1,le=1); maximum_pages:int=Field(default=5,ge=1,le=5)
    maximum_depth:int=Field(default=1,ge=0,le=1); timeout_seconds:int=Field(default=30,ge=5,le=60)
    minimum_domain_delay_seconds:float=Field(default=2,ge=2,le=30); maximum_page_bytes:int=Field(default=1_000_000,ge=10_000,le=2_000_000)
    maximum_total_bytes:int=Field(default=3_000_000,ge=10_000,le=5_000_000); maximum_redirects:int=Field(default=3,ge=0,le=5)
class WebResearchPlan(AuraBaseModel):
    plan_id:UUID=Field(default_factory=uuid4); objective:str=Field(min_length=1,max_length=1000); research_question:str=Field(min_length=1,max_length=1000)
    approved_domains:list[str]=Field(min_length=1,max_length=10); expected_official_sources:list[str]=Field(default_factory=list,max_length=10)
    adapter_rationale:str=Field(min_length=1,max_length=1000); limits:CrawlLimits=Field(default_factory=CrawlLimits)
    expected_evidence:list[str]=Field(default_factory=list,max_length=20); prohibited_actions:list[str]=Field(default_factory=list)
    data_retention_policy:str="Bounded excerpts and metadata only; no full articles."
    founder_approval_status:ApprovalState=ApprovalState.PENDING; plan_hash:str=Field(default="",pattern=r"^(?:|[a-f0-9]{64})$")
    created_at:datetime=Field(default_factory=utc_now); expires_at:datetime=Field(default_factory=lambda:utc_now()+timedelta(hours=24))
    @model_validator(mode="after")
    def expiry_valid(self):
        if self.expires_at<=self.created_at: raise ValueError("Plan expiry must follow creation.")
        return self
class PlanApproval(AuraBaseModel):
    approval_id:UUID=Field(default_factory=uuid4); plan_id:UUID; plan_hash:str=Field(pattern=r"^[a-f0-9]{64}$")
    approved_domains:list[str]=Field(min_length=1); state:ApprovalState=ApprovalState.APPROVED
    approved_at:datetime=Field(default_factory=utc_now); expires_at:datetime
class AdapterStatus(AuraBaseModel):
    kind:AdapterKind; available:bool; reason:str; version:str|None=None; external_operations_enabled:bool=False
class EvidenceItem(AuraBaseModel):
    evidence_id:UUID=Field(default_factory=uuid4); source_url:str; canonical_url:str; page_title:str=Field(max_length=500); publisher_domain:str
    publication_date:datetime|None=None; accessed_at:datetime=Field(default_factory=utc_now); supporting_excerpt:str=Field(max_length=500)
    surrounding_summary:str=Field(max_length=1500); extraction_method:AdapterKind; content_hash:str=Field(pattern=r"^[a-f0-9]{64}$")
    classification:EvidenceClassification; confidence:float=Field(ge=0,le=1); robots_allowed:bool; page_freshness:str
    screenshot_reference:Path|None=None
class Citation(AuraBaseModel):
    citation_id:UUID=Field(default_factory=uuid4); evidence_id:UUID; title:str; url:str; publisher:str; accessed_at:datetime
class AdapterRequest(AuraBaseModel):
    plan_id:UUID; plan_hash:str; url:str; mode:OperatingMode; founder_confirmed:bool=False
class AdapterResult(AuraBaseModel):
    adapter:AdapterKind; canonical_url:str; title:str; content_type:str; content_bytes:int=Field(ge=0); excerpt:str=Field(max_length=500); metadata:dict[str,Any]=Field(default_factory=dict)
class DashboardState(AuraBaseModel):
    mode:OperatingMode=OperatingMode.OFFLINE; adapters:list[AdapterStatus]; pending_plans:int=0; approved_domains:list[str]=Field(default_factory=list)
    limits:CrawlLimits=Field(default_factory=CrawlLimits); robots_enforced:bool=True; evidence_count:int=0; citation_count:int=0
    blocked_actions:list[str]=Field(default_factory=list); risk_alerts:list[str]=Field(default_factory=list); founder_approval_status:ApprovalState=ApprovalState.PENDING
    read_only:bool=True; login_allowed:bool=False; publishing_allowed:bool=False
