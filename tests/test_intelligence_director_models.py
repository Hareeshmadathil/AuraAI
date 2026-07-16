from datetime import datetime
from uuid import uuid4
import pytest
from pydantic import ValidationError
from intelligence_director.fixtures import synthetic_signals
from intelligence_director.models import IntelligenceSignal,WebResearchPlanRequest
from intelligence_director.enums import ResearchDepth

def test_signal_is_strict_aware_and_hash_bearing():
    signal=synthetic_signals()[0]
    assert len(signal.content_hash)==64
    with pytest.raises(ValidationError): IntelligenceSignal.model_validate({**signal.model_dump(),"observed_at":datetime.now(),"content_hash":""})
    with pytest.raises(ValidationError): IntelligenceSignal.model_validate({**signal.model_dump(),"unexpected":True})
def test_web_plan_cannot_enable_live_execution():
    with pytest.raises(ValidationError): WebResearchPlanRequest(objective="x",research_question="x",priority=1,research_depth=ResearchDepth.QUICK,approved_domains=["example.com"],official_sources_expected=[],maximum_pages=1,maximum_duration_seconds=10,expected_evidence=[],prohibited_actions=[],freshness_deadline=synthetic_signals()[0].observed_at,live_execution=True)
