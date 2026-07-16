"""Citation projection without article bodies."""
from web_intelligence.models import Citation,EvidenceItem
def citation_for(item:EvidenceItem)->Citation:
    return Citation(evidence_id=item.evidence_id,title=item.page_title,url=item.canonical_url,publisher=item.publisher_domain,accessed_at=item.accessed_at)
