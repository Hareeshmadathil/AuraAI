"""Bounded evidence creation retaining provenance."""
import hashlib
from urllib.parse import urlparse
from web_intelligence.enums import AdapterKind,EvidenceClassification
from web_intelligence.models import EvidenceItem
def create_evidence(*,url:str,canonical_url:str,title:str,excerpt:str,summary:str,method:AdapterKind,
                    classification:EvidenceClassification=EvidenceClassification.UNVERIFIED,confidence:float=.5,
                    robots_allowed:bool=True,freshness:str="unknown")->EvidenceItem:
    bounded=excerpt.strip()[:500]
    return EvidenceItem(source_url=url,canonical_url=canonical_url,page_title=title[:500],publisher_domain=(urlparse(canonical_url).hostname or ""),
        supporting_excerpt=bounded,surrounding_summary=summary[:1500],extraction_method=method,
        content_hash=hashlib.sha256(bounded.encode()).hexdigest(),classification=classification,confidence=confidence,
        robots_allowed=robots_allowed,page_freshness=freshness)
