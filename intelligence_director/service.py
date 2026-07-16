"""Recommendation-only Intelligence Director orchestration."""
from intelligence_director.contradiction_detection import detect_contradiction
from intelligence_director.competitor_priority import score_competitor
from intelligence_director.evidence_weighting import weigh_claim
from intelligence_director.freshness import assess_freshness
from intelligence_director.handoff import create_content_context,create_web_plan_request
from intelligence_director.memory_policy import decide_retention
from intelligence_director.models import *
from intelligence_director.queue import build_queue
from intelligence_director.recommendation import recommend
from intelligence_director.research_depth import recommend_depth
from intelligence_director.research_priority import score_priority
from intelligence_director.source_authority import assess_source
class IntelligenceDirectorService:
    """Analyze supplied signals offline; never execute research or missions."""
    def analyze(self,signals:list[IntelligenceSignal])->IntelligenceResult:
        if not signals: raise ValueError("At least one signal is required.")
        if len(signals)>1000: raise ValueError("Signal import exceeds the bounded limit.")
        if len({x.signal_id for x in signals})!=len(signals): raise ValueError("Duplicate signal IDs are forbidden.")
        run=IntelligenceRun(signal_ids=[x.signal_id for x in signals]); scores=[]; items=[]
        authorities=[assess_source(x.evidence_references[0] if x.evidence_references else "unreferenced", "official_primary" if x.verification_status==VerificationStatus.VERIFIED else "community", stale="stale" in x.topic.casefold(), region_mismatch="region" in x.topic.casefold()) for x in signals]
        for signal in signals:
            candidate=ResearchCandidate(signal_ids=[signal.signal_id],question=ResearchQuestion(text=f"What evidence verifies {signal.topic}?"),objective=ResearchObjective(description=f"Resolve evidence and freshness for {signal.topic}",success_evidence=["Current applicable source"]),duplicate_topic="duplicated" in signal.topic.casefold(),verification_cost=80 if "privacy" in signal.topic.casefold() else 30)
            score=score_priority(candidate,signal,safety_compliance_risk=100 if "privacy" in signal.topic.casefold() else 0,contradiction_severity=90 if "conflicting" in signal.topic.casefold() else 0)
            if "privacy" in signal.topic.casefold(): score=score.model_copy(update={"band":PriorityBand.REJECT,"rationale":score.rationale+["Privacy or safety risk is prohibited"]})
            depth=recommend_depth(score); scores.append(score)
            items.append(ResearchQueueItem(order=1,research_question=candidate.question,priority_score=score,assigned_system="Existing Research Director / Web Intelligence",recommended_depth=depth,approved_domains=["example.com"],expected_evidence=depth.expected_evidence,expires_at=depth.freshness_deadline,execution_status=QueueStatus.REJECTED if score.band==PriorityBand.REJECT else QueueStatus.AWAITING))
        queue=build_queue(items); top_index=max(range(len(scores)),key=lambda i:scores[i].overall); top=signals[top_index]; depth=items[top_index].recommended_depth
        contradictions=[]
        for signal in signals:
            if "conflicting" in signal.topic.casefold() or "region" in signal.topic.casefold(): contradictions.append(detect_contradiction(EvidenceConflict(claim_a=signal.summary,claim_b="Alternative synthetic claim",source_references=signal.evidence_references)))
        plan=create_web_plan_request(top,scores[top_index],depth,["example.com"])
        context=create_content_context(top,verified_facts=[top.summary] if top.verification_status==VerificationStatus.VERIFIED else [],unresolved=[] if top.verification_status==VerificationStatus.VERIFIED else [top.summary],prohibited=["Guaranteed reach or revenue"],deadline=depth.freshness_deadline)
        freshness=[assess_freshness(x,"pricing" if "pricing" in x.topic.casefold() else "general") for x in signals]
        evidence=[weigh_claim(x.summary,[a] if x.verification_status==VerificationStatus.VERIFIED else [],[a] if x.verification_status==VerificationStatus.DISPUTED else []) for x,a in zip(signals,authorities)]
        competitor=CompetitorResearchCandidate(name="Synthetic competitor candidate",approved_public_domains=["example.com"],permitted_questions=["What public positioning is documented?"],audience_overlap=60,topic_overlap=65,strategic_relevance=70,research_cost=30)
        retention=[decide_retention(x.signal_id,x.verification_status,ContradictionStatus.UNRESOLVED if any(x.topic in claim for group in contradictions for claim in group.affected_claims) else ContradictionStatus.NONE,f.expires_at,private_data="privacy" in x.topic.casefold()) for x,f in zip(signals,freshness)]
        return IntelligenceResult(run=run,signals=signals,authority_assessments=authorities,evidence_weights=evidence,priorities=scores,competitor_priorities=[score_competitor(competitor)],contradictions=contradictions,freshness=freshness,retention_decisions=retention,recommendations=[recommend(x) for x in scores],queue=queue,web_plan_request=plan,content_context=context)
