"""Bounded research-depth recommendation."""
from datetime import timedelta
from core import utc_now
from intelligence_director.enums import ResearchDepth
from intelligence_director.models import ResearchDepthRecommendation,ResearchPriorityScore
def recommend_depth(score:ResearchPriorityScore)->ResearchDepthRecommendation:
    depth=ResearchDepth.DEEP if score.overall>=75 else ResearchDepth.STANDARD if score.overall>=55 else ResearchDepth.QUICK if score.overall>=35 else ResearchDepth.NONE
    pages={ResearchDepth.DEEP:5,ResearchDepth.STANDARD:4,ResearchDepth.QUICK:2,ResearchDepth.NONE:0}[depth]
    return ResearchDepthRecommendation(depth=depth,rationale=[f"Priority score {score.overall:.2f}"],expected_sources=["Current official source","Independent corroboration"],maximum_pages=pages,maximum_duration_seconds=min(60,pages*12),required_official_sources=1 if pages else 0,competitor_sources_allowed=pages>=4,contradiction_checks=["region","version","pricing"],freshness_deadline=utc_now()+timedelta(days=1),stop_conditions=["robots denial","login required","sufficient evidence","resource limit"],expected_evidence=["bounded excerpts","citations","freshness metadata"],founder_approval_required=True)
