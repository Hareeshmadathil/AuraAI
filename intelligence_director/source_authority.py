"""Explainable source-authority assessment without popularity metrics."""
from intelligence_director.enums import AuthorityUse
from intelligence_director.models import SourceAuthorityAssessment

BASE={"official_primary":95,"official_documentation":90,"first_party_data":85,"reputable_secondary":75,"independent_analysis":65,"founder_supplied":60,"community":30,"anonymous":10}
def assess_source(reference:str,category:str,*,stale:bool=False,region_mismatch:bool=False,corrected:bool=False)->SourceAuthorityAssessment:
    score=float(BASE.get(category,10))- (25 if stale else 0)-(15 if region_mismatch else 0)-(30 if corrected else 0)
    score=max(0,score); usage=AuthorityUse.FACTUAL if score>=75 and not stale else AuthorityUse.CONTEXT if score>=45 else AuthorityUse.DEMAND if score>=20 else AuthorityUse.PROHIBITED
    limitations=[x for x,active in (("Information is stale",stale),("Region applicability differs",region_mismatch),("Correction or retraction history",corrected)) if active]
    return SourceAuthorityAssessment(source_reference=reference,category=category,authority_score=score,confidence=min(.95,max(.2,score/100)),reasons=["Category-based authority; popularity is not scored"],limitations=limitations,required_verification=[] if usage==AuthorityUse.FACTUAL else ["Verify against a current applicable primary source"],allowed_usage=usage,region_mismatch=region_mismatch,stale=stale)
