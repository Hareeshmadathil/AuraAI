"""Privacy-safe competitor prioritization."""
from intelligence_director.models import CompetitorPriorityScore,CompetitorResearchCandidate
def score_competitor(c:CompetitorResearchCandidate)->CompetitorPriorityScore:
    score=round(.35*c.audience_overlap+.25*c.topic_overlap+.3*c.strategic_relevance-.1*c.research_cost,2)
    return CompetitorPriorityScore(competitor_id=c.competitor_id,score=max(0,min(100,score)),rationale=["Public, verified evidence only","Research cost is penalized"],approved_public_domains=c.approved_public_domains,evidence_required=["Founder-supplied or existing public evidence"],refresh_cadence_days=30)
