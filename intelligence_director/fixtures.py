"""Clearly synthetic deterministic demonstration signals."""
from datetime import timedelta
from core import utc_now
from intelligence_director.enums import SignalSource,VerificationStatus
from intelligence_director.models import IntelligenceSignal,SignalContext
def synthetic_signals()->list[IntelligenceSignal]:
    specs=[
        ("Viral AI claim","Weak community evidence",.2,90,24,False),("Official product announcement","Verified official summary",.95,80,48,True),("Conflicting pricing claims","Two incompatible prices",.45,85,24,False),("Stale free trial","Old trial information",.5,70,12,False),("Evergreen tutorial","Stable educational concept",.85,55,2160,True),("Competitor candidate","Public positioning question",.6,50,168,False),("Duplicated topic","Low-value repeated question",.5,20,168,False),("Region availability","Availability differs by region",.5,75,24,False),("Platform policy change","Urgent policy verification",.8,100,12,True),("Privacy-risk request","Private analytics collection prohibited",.1,95,24,False)]
    now=utc_now()
    return [IntelligenceSignal(source=SignalSource.FIXTURE,source_name="Synthetic deterministic fixture",topic=t,summary=s,entities=[],evidence_references=["synthetic://fixture"],observed_at=now-(timedelta(days=10) if "Stale" in t else timedelta()),freshness_window_hours=f,context=SignalContext(business_relevance=70,audience_relevance=65,urgency=u),confidence=c,verification_status=VerificationStatus.VERIFIED if v else VerificationStatus.UNVERIFIED,synthetic=True) for t,s,c,u,f,v in specs]
