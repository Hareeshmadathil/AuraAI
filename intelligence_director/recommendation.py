"""Safe recommendation creation."""
from intelligence_director.models import IntelligenceRecommendation,ResearchPriorityScore
def recommend(score:ResearchPriorityScore)->IntelligenceRecommendation:
    return IntelligenceRecommendation(action=score.band.value,rationale=score.rationale+["Founder decision is required"],confidence=min(.9,score.overall/100))
