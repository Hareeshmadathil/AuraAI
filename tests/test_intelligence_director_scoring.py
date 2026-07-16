from intelligence_director.contradiction_detection import detect_contradiction
from intelligence_director.enums import AuthorityUse,ContradictionStatus
from intelligence_director.evidence_weighting import weigh_claim
from intelligence_director.models import EvidenceConflict
from intelligence_director.source_authority import assess_source

def test_official_outranks_community_and_popularity_is_irrelevant():
    official=assess_source("official.example","official_primary")
    community=assess_source("forum.example","community")
    assert official.authority_score>community.authority_score
    assert official.allowed_usage==AuthorityUse.FACTUAL
def test_stale_and_region_mismatch_are_surfaced():
    result=assess_source("docs.example","official_documentation",stale=True,region_mismatch=True)
    assert result.stale and result.region_mismatch and result.allowed_usage!=AuthorityUse.FACTUAL
def test_opposition_is_not_averaged_away():
    a=assess_source("a.example","official_primary"); b=assess_source("b.example","reputable_secondary")
    weighted=weigh_claim("price",[a],[b])
    assert weighted.total_opposition_weight>0 and weighted.further_research_required
def test_region_and_version_conflicts_are_preserved():
    region=detect_contradiction(EvidenceConflict(claim_a="US only",claim_b="India available",source_references=["a","b"]))
    version=detect_contradiction(EvidenceConflict(claim_a="release date 2025",claim_b="release date 2026",source_references=["a","b"]))
    assert region.status==ContradictionStatus.REGION
    assert version.status==ContradictionStatus.VERSION and version.blocks_content_production
