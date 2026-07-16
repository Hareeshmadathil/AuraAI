"""Offline adapter, evidence, and deterministic output tests."""
import json
from pathlib import Path
import pytest
from web_intelligence.adapters import HttpPublicAdapter
from web_intelligence.enums import AdapterKind,EvidenceClassification,OperatingMode
from web_intelligence.evidence import create_evidence
from web_intelligence.exceptions import ResourceLimitError
from web_intelligence.exporter import WebReportExporter
from web_intelligence.fixtures.public_demo_pages import demo_fetcher
from web_intelligence.models import AdapterRequest
from web_intelligence.url_safety import UrlSafetyValidator

def adapter(fetcher=demo_fetcher,maximum=1_000_000):
    return HttpPublicAdapter(UrlSafetyValidator(["example.com"],resolver=lambda host:["93.184.216.34"]),fetcher,maximum)
def request(): return AdapterRequest(plan_id="00000000-0000-0000-0000-000000000001",plan_hash="a"*64,url="https://example.com/",mode=OperatingMode.PUBLIC_READ_ONLY,founder_confirmed=True)
def test_http_fixture_and_duplicate_safe_result():
    result=adapter().execute(request()); assert result.adapter==AdapterKind.HTTP_PUBLIC and result.content_bytes>0
def test_content_type_and_size_bounds():
    with pytest.raises(ResourceLimitError): adapter(lambda url,size:(url,"application/octet-stream",b"x")).execute(request())
    with pytest.raises(ResourceLimitError): adapter(lambda url,size:(url,"text/html",b"x"*20),10).execute(request())
def test_evidence_and_citation_export_are_bounded(tmp_path:Path):
    item=create_evidence(url="https://example.com/",canonical_url="https://example.com/",title="Example",excerpt="x"*900,
        summary="summary",method=AdapterKind.HTTP_PUBLIC,classification=EvidenceClassification.PUBLIC_PRIMARY)
    assert len(item.supporting_excerpt)==500 and len(item.content_hash)==64
    from web_intelligence.citations import citation_for
    path=WebReportExporter(tmp_path).export_report([item],[citation_for(item)])
    payload=json.loads(path.read_text()); assert payload["citations"][0]["url"]=="https://example.com/"
def test_export_path_traversal_rejected(tmp_path:Path):
    with pytest.raises(Exception): WebReportExporter(tmp_path).export_report([],[],"../outside.json")
