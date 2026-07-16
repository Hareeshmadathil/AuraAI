"""Synthetic and internally derived knowledge fixtures."""
from datetime import timedelta
from uuid import uuid4
from core import utc_now
from intelligence_director.enums import VerificationStatus
from knowledge_manager.approvals import evidence_hash
from knowledge_manager.enums import *
from knowledge_manager.models import *
from knowledge_manager.normalization import canonical_claim,normalize_text
SPECS=[
("Gemini structured JSON","Gemini structured JSON passed an injected smoke test.",KnowledgeCategory.PROVIDER_RELIABILITY,True),("Nemotron compatibility","Nemotron structured output remains experimental.",KnowledgeCategory.PROVIDER_RELIABILITY,False),("Provider free plan","Provider free-plan information requires refresh.",KnowledgeCategory.PRICING,False),("ElevenLabs voice","Founder selected an installed voice for internal preparation.",KnowledgeCategory.FOUNDER_DECISION,True),("Subtitle correction","A 43-character subtitle line failed validation and was corrected.",KnowledgeCategory.PRODUCTION_LESSON,True),("Mission Zero revision","Mission Zero required a quality revision.",KnowledgeCategory.HISTORICAL,True),("Regional availability","A product is available only in one synthetic region.",KnowledgeCategory.PRODUCT_AVAILABILITY,False),("Superseded pricing","A synthetic former price is no longer current.",KnowledgeCategory.PRICING,False),("Evergreen tutorial","Explain concepts before implementation steps.",KnowledgeCategory.TUTORIAL,True),("Private record","Synthetic private customer banking record.",KnowledgeCategory.PRIVATE,False),("Duplicate Gemini","Gemini structured JSON passed an injected smoke test.",KnowledgeCategory.PROVIDER_RELIABILITY,True),("Engineering decision","Use immutable typed artifacts for history.",KnowledgeCategory.ENGINEERING_DECISION,True)]
def fixture_requests()->list[KnowledgeIngestionRequest]:
    now=utc_now(); requests=[]
    for index,(topic,claim,category,approved) in enumerate(SPECS):
        knowledge_id=uuid4(); source_hash=hash_value({"fixture":index}); claim_model=KnowledgeClaim(text=claim,canonical_text=canonical_claim(claim),confidence=.9 if approved else .5,verification_status=VerificationStatus.VERIFIED if approved else VerificationStatus.UNVERIFIED)
        source=KnowledgeSourceReference(source_system=SourceSystem.FIXTURE,artifact_id=f"fixture-{index}",artifact_hash=source_hash,locator="synthetic://knowledge-fixture",evidence_class=EvidenceClass.INTERNAL,authority_score=80 if approved else 40,observed_at=now-timedelta(days=10 if index in {2,7} else 0))
        freshness=KnowledgeFreshness(observed_at=source.observed_at,valid_from=source.observed_at,last_verified_at=source.observed_at if approved else None,refresh_after=source.observed_at+timedelta(days=1 if category in {KnowledgeCategory.PRICING,KnowledgeCategory.PRODUCT_AVAILABILITY} else 30),expires_at=source.observed_at+timedelta(days=3 if category in {KnowledgeCategory.PRICING,KnowledgeCategory.PRODUCT_AVAILABILITY} else 365),status=FreshnessStatus.EXPIRED if index in {2,7} else FreshnessStatus.FRESH)
        retention=KnowledgeRetentionPolicy(action=RetentionAction.PROHIBITED if category==KnowledgeCategory.PRIVATE else RetentionAction.VERIFIED if approved else RetentionAction.TEMPORARY,maximum_retention_days=365,founder_approval_required=approved,rationale="Synthetic bounded fixture policy")
        version=KnowledgeVersion(knowledge_id=knowledge_id,version=1,topic=KnowledgeTopic(name=topic,normalized_name=normalize_text(topic),tags=["synthetic"]),category=category,claims=[claim_model],entities=[],summary=claim,sources=[source],evidence_links=[],freshness=freshness,retention_policy=retention,approval_status=ApprovalStatus.APPROVED if approved else ApprovalStatus.PENDING,created_by="deterministic fixture")
        approval=KnowledgeApproval(version_id=version.version_id,content_hash=version.content_hash,evidence_hash=evidence_hash(version),retention_action=retention.action,expires_at=now+timedelta(days=1),approver_role="Founder fixture",decision=FounderDecision.APPROVE) if approved else None
        requests.append(KnowledgeIngestionRequest(source_system=SourceSystem.FIXTURE,source_artifact_id=source.artifact_id,source_artifact_hash=source_hash,proposed_version=version,founder_approval=approval,private_data_risk=category==KnowledgeCategory.PRIVATE))
    return requests
