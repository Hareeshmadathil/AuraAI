"""Deterministic claim evidence weighting."""
from intelligence_director.enums import VerificationStatus
from intelligence_director.models import EvidenceWeight,SourceAuthorityAssessment
def weigh_claim(claim:str,supporting:list[SourceAuthorityAssessment],opposing:list[SourceAuthorityAssessment])->EvidenceWeight:
    def total(values):
        seen=set(); result=0.0
        for item in values:
            domain=item.source_reference.casefold(); factor=.5 if domain in seen else 1; seen.add(domain); result+=item.authority_score*factor
        return min(100,round(result/max(1,len(values)),2)) if values else 0
    support,opposition=total(supporting),total(opposing); conflict=opposition>=25
    confidence=min(.95,round(max(support,opposition)/100*(.6 if conflict else 1),2))
    status=VerificationStatus.DISPUTED if conflict else VerificationStatus.VERIFIED if support>=70 else VerificationStatus.PARTIAL
    return EvidenceWeight(claim=claim,supporting_evidence=[x.source_reference for x in supporting],opposing_evidence=[x.source_reference for x in opposing],total_support_weight=support,total_opposition_weight=opposition,confidence=confidence,verification_status=status,allowed_wording=["Evidence indicates"] if status!=VerificationStatus.DISPUTED else ["Sources conflict"],prohibited_wording=["proven","guaranteed","certain"],further_research_required=status!=VerificationStatus.VERIFIED)
