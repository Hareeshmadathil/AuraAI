"""Preserve conflicting claims and classify material differences."""
from intelligence_director.enums import ContradictionStatus
from intelligence_director.models import ContradictionGroup,EvidenceConflict
def detect_contradiction(conflict:EvidenceConflict)->ContradictionGroup:
    text=f"{conflict.claim_a} {conflict.claim_b}".casefold()
    status=ContradictionStatus.REGION if any(x in text for x in ("region","country","india","us only")) else ContradictionStatus.VERSION if any(x in text for x in ("version","release date","outdated")) else ContradictionStatus.CORRECTED if any(x in text for x in ("retracted","corrected","withdrawn")) else ContradictionStatus.MATERIAL
    blocks=status in {ContradictionStatus.MATERIAL,ContradictionStatus.VERSION}
    return ContradictionGroup(status=status,summary="Conflicting evidence must be preserved and verified.",affected_claims=[conflict.claim_a,conflict.claim_b],source_references=conflict.source_references,recommended_wording="Sources disagree; current applicability is unverified.",founder_verification_checklist=["Check current official source","Confirm region and version"],blocks_content_production=blocks)
