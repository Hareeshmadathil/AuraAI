"""Strict typed, versioned knowledge artifacts."""
from __future__ import annotations
import hashlib,json
from datetime import datetime
from typing import Any
from uuid import UUID,uuid4
from pydantic import Field,field_validator,model_validator
from core import AuraBaseModel,utc_now
from intelligence_director.enums import VerificationStatus
from knowledge_manager.enums import *
def hash_value(value:Any,exclude:set[str]|None=None)->str:
    if hasattr(value,"model_dump"): value=value.model_dump(mode="json",exclude=exclude or set())
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def aware(v):
    if v is not None and (v.tzinfo is None or v.utcoffset() is None): raise ValueError("Timestamp must be timezone-aware.")
    return v
class KnowledgeTopic(AuraBaseModel): name:str=Field(min_length=1,max_length=300); normalized_name:str=Field(min_length=1,max_length=300); tags:list[str]=Field(default_factory=list,max_length=20)
class KnowledgeEntity(AuraBaseModel): name:str=Field(min_length=1,max_length=200); normalized_name:str=Field(min_length=1,max_length=200); entity_type:str=Field(max_length=50); aliases:list[str]=Field(default_factory=list,max_length=20)
class KnowledgeClaim(AuraBaseModel): claim_id:UUID=Field(default_factory=uuid4); text:str=Field(min_length=1,max_length=1000); canonical_text:str=Field(min_length=1,max_length=1000); region:str|None=Field(default=None,max_length=100); confidence:float=Field(ge=0,le=1); verification_status:VerificationStatus
class KnowledgeSourceReference(AuraBaseModel):
    source_id:UUID=Field(default_factory=uuid4); source_system:SourceSystem; artifact_id:str=Field(min_length=1,max_length=200); artifact_hash:str=Field(pattern=r"^[a-f0-9]{64}$"); locator:str=Field(max_length=500); evidence_class:EvidenceClass; authority_score:float=Field(ge=0,le=100); observed_at:datetime
    _observed=field_validator("observed_at")(aware)
class KnowledgeEvidenceLink(AuraBaseModel): link_id:UUID=Field(default_factory=uuid4); claim_id:UUID; source_id:UUID; excerpt:str=Field(max_length=500); evidence_hash:str=Field(pattern=r"^[a-f0-9]{64}$")
class KnowledgeFreshness(AuraBaseModel):
    observed_at:datetime; valid_from:datetime; last_verified_at:datetime|None=None; refresh_after:datetime; expires_at:datetime; status:FreshnessStatus
    _times=field_validator("observed_at","valid_from","last_verified_at","refresh_after","expires_at")(aware)
class KnowledgeRetentionPolicy(AuraBaseModel): action:RetentionAction; maximum_retention_days:int=Field(ge=0,le=36500); founder_approval_required:bool; rationale:str=Field(max_length=500)
class KnowledgeRetentionDecision(AuraBaseModel): decision_id:UUID=Field(default_factory=uuid4); knowledge_id:UUID; action:RetentionAction; rationale:list[str]; decided_at:datetime=Field(default_factory=utc_now)
class KnowledgeVersion(AuraBaseModel):
    version_id:UUID=Field(default_factory=uuid4); knowledge_id:UUID; version:int=Field(ge=1); parent_version_id:UUID|None=None; topic:KnowledgeTopic; category:KnowledgeCategory; claims:list[KnowledgeClaim]=Field(min_length=1,max_length=30); entities:list[KnowledgeEntity]=Field(default_factory=list,max_length=30); summary:str=Field(min_length=1,max_length=2000); sources:list[KnowledgeSourceReference]=Field(min_length=1,max_length=30); evidence_links:list[KnowledgeEvidenceLink]=Field(default_factory=list,max_length=50); freshness:KnowledgeFreshness; conflict_status:ConflictStatus=ConflictStatus.NONE; content_hash:str=Field(default="",pattern=r"^(?:|[a-f0-9]{64})$"); retention_policy:KnowledgeRetentionPolicy; approval_status:ApprovalStatus=ApprovalStatus.PENDING; created_by:str=Field(min_length=1,max_length=100); created_at:datetime=Field(default_factory=utc_now); superseded_by:UUID|None=None
    @model_validator(mode="after")
    def validate_version(self):
        if self.version>1 and self.parent_version_id is None: raise ValueError("Updated versions require a parent.")
        expected=hash_value(self,{"content_hash","superseded_by"})
        if self.content_hash and self.content_hash!=expected: raise ValueError("Knowledge version hash mismatch.")
        object.__setattr__(self,"content_hash",expected); return self
class KnowledgeItem(AuraBaseModel): knowledge_id:UUID=Field(default_factory=uuid4); current_version_id:UUID; created_at:datetime=Field(default_factory=utc_now); archived_at:datetime|None=None
class KnowledgeConflict(AuraBaseModel): conflict_id:UUID=Field(default_factory=uuid4); knowledge_id:UUID; version_ids:list[UUID]=Field(min_length=2); status:ConflictStatus; affected_claims:list[str]; evidence_ids:list[UUID]; allowed_wording:list[str]; prohibited_wording:list[str]; factual_use_blocked:bool
class KnowledgeApproval(AuraBaseModel):
    approval_id:UUID=Field(default_factory=uuid4); version_id:UUID; content_hash:str=Field(pattern=r"^[a-f0-9]{64}$"); evidence_hash:str=Field(pattern=r"^[a-f0-9]{64}$"); retention_action:RetentionAction; expires_at:datetime; approver_role:str; decision:FounderDecision; decided_at:datetime=Field(default_factory=utc_now)
    _times=field_validator("expires_at","decided_at")(aware)
class KnowledgeQueryFilter(AuraBaseModel): category:KnowledgeCategory|None=None; verification_status:VerificationStatus|None=None; freshness:FreshnessStatus|None=None; source_type:SourceSystem|None=None; minimum_confidence:float=Field(default=0,ge=0,le=1); region:str|None=None; current_only:bool=True; founder_approved_only:bool=False
class KnowledgeQuery(AuraBaseModel): text:str=Field(min_length=1,max_length=500); entities:list[str]=Field(default_factory=list,max_length=20); filters:KnowledgeQueryFilter=Field(default_factory=KnowledgeQueryFilter); limit:int=Field(default=10,ge=1,le=50)
class KnowledgeMatch(AuraBaseModel): version:KnowledgeVersion; relevance_score:float=Field(ge=0,le=100); score_explanation:dict[str,float]; current:bool; freshness_warnings:list[str]; conflicts:list[UUID]; allowed_usage:str; required_verification:list[str]
class KnowledgeRetrievalResult(AuraBaseModel): query:KnowledgeQuery; matches:list[KnowledgeMatch]; total_considered:int=Field(ge=0); executed_at:datetime=Field(default_factory=utc_now)
class KnowledgeIngestionRequest(AuraBaseModel): request_id:UUID=Field(default_factory=uuid4); source_system:SourceSystem; source_artifact_id:str; source_artifact_hash:str=Field(pattern=r"^[a-f0-9]{64}$"); proposed_version:KnowledgeVersion; founder_approval:KnowledgeApproval|None=None; private_data_risk:bool=False
class KnowledgeIngestionResult(AuraBaseModel): request_id:UUID; accepted:bool; knowledge_id:UUID|None=None; version_id:UUID|None=None; duplicate_kind:DuplicateKind; reasons:list[str]; founder_review_required:bool
class KnowledgeUpdateProposal(AuraBaseModel): proposal_id:UUID=Field(default_factory=uuid4); knowledge_id:UUID; parent_version_id:UUID; proposed_version:KnowledgeVersion; added_claims:list[str]; removed_claims:list[str]; changed_claims:list[str]
class KnowledgeArchiveRecord(AuraBaseModel): archive_id:UUID=Field(default_factory=uuid4); knowledge_id:UUID; version_id:UUID; reason:str; archived_at:datetime=Field(default_factory=utc_now)
class KnowledgeAuditEntry(AuraBaseModel): audit_id:UUID=Field(default_factory=uuid4); action:str; knowledge_id:UUID|None=None; version_id:UUID|None=None; safe_metadata:dict[str,Any]=Field(default_factory=dict); timestamp:datetime=Field(default_factory=utc_now)
class RefreshQueueItem(AuraBaseModel):
    knowledge_id:UUID; reason:str; priority:float=Field(ge=0,le=100); expected_source_type:str; deadline:datetime; previous_verification_date:datetime|None=None; risk_if_not_refreshed:str; intelligence_director_handoff:str
    _times=field_validator("deadline","previous_verification_date")(aware)
class OwnedContentPerformance(AuraBaseModel):
    video_id:str=Field(min_length=1,max_length=200); platform:str=Field(min_length=1,max_length=100); title_version:str; thumbnail_version:str; hook_version:str; publication_date:datetime; impressions:int=Field(ge=0); click_through_rate:float=Field(ge=0,le=100); watch_time_seconds:float=Field(ge=0); retention_checkpoints:dict[str,float]; engagement:int=Field(ge=0); conversions:int=Field(ge=0); revenue:float|None=Field(default=None,ge=0); metric_source:str; imported_at:datetime=Field(default_factory=utc_now); founder_supplied:bool=True
    _times=field_validator("publication_date","imported_at")(aware)
class KnowledgeContextPackage(AuraBaseModel): current_verified_facts:list[str]; qualified_facts:list[str]; freshness_warnings:list[str]; unresolved_claims:list[str]; prohibited_claims:list[str]; source_references:list[str]; evidence_visuals:list[str]; confidence:float=Field(ge=0,le=1); expiry_deadline:datetime|None=None; founder_review_status:ApprovalStatus; mission_executed:bool=False; rendered:bool=False; published:bool=False
class KnowledgeManagerRun(AuraBaseModel): run_id:UUID=Field(default_factory=uuid4); started_at:datetime=Field(default_factory=utc_now); offline:bool=True; synthetic:bool=False
class KnowledgeManagerResult(AuraBaseModel): run:KnowledgeManagerRun; item_count:int; current_versions:int; historical_versions:int; conflicts:list[KnowledgeConflict]; refresh_queue:list[RefreshQueueItem]; retrieval:KnowledgeRetrievalResult|None=None; context:KnowledgeContextPackage|None=None; completed_at:datetime=Field(default_factory=utc_now); live_research:bool=False; mission_executed:bool=False; rendered:bool=False; published:bool=False
