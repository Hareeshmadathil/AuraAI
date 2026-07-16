"""Offline adapter, evidence, and deterministic output tests."""
import json
from pathlib import Path
import pytest
from web_intelligence.adapters import HttpPublicAdapter
from web_intelligence.adapters.crawl4ai_adapter import (
    INSTALLED_REASON,
    PINNED_VERSION,
    InstalledCrawl4AIAdapter,
    create_crawl4ai_adapter,
)
from web_intelligence.adapters.unavailable import UnavailableAdapter
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


def test_crawl4ai_missing_returns_unavailable(monkeypatch):
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.importlib.util.find_spec",
        lambda name: None,
    )
    value = create_crawl4ai_adapter()
    assert isinstance(value, UnavailableAdapter)
    assert value.status.available is False
    assert value.status.external_operations_enabled is False


def test_crawl4ai_matching_install_is_available_but_execution_blocked(monkeypatch):
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.importlib.util.find_spec",
        lambda name: object(),
    )
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.metadata.version",
        lambda name: PINNED_VERSION,
    )
    value = create_crawl4ai_adapter()
    assert isinstance(value, InstalledCrawl4AIAdapter)
    assert value.status.available is True
    assert value.status.external_operations_enabled is False
    assert value.status.version == PINNED_VERSION
    assert value.status.reason == INSTALLED_REASON
    with pytest.raises(Exception) as error:
        value.execute(request())
    assert getattr(error.value, "error_code", "") == "CRAWL4AI_RUNTIME_REQUIRED"


def test_crawl4ai_version_mismatch_reports_actual_version(monkeypatch):
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.importlib.util.find_spec",
        lambda name: object(),
    )
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.metadata.version",
        lambda name: "9.9.9",
    )
    value = create_crawl4ai_adapter()
    assert value.status.available is True
    assert value.status.external_operations_enabled is False
    assert value.status.version == "9.9.9"
    assert "pinned version is 0.9.1" in value.status.reason


def test_crawl4ai_detection_has_no_runtime_or_network_side_effect(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.importlib.util.find_spec",
        lambda name: object(),
    )
    monkeypatch.setattr(
        "web_intelligence.adapters.crawl4ai_adapter.metadata.version",
        lambda name: PINNED_VERSION,
    )
    value = create_crawl4ai_adapter(runtime=lambda request: calls.append(request))
    assert calls == []
    assert "crawl4ai" not in __import__("sys").modules
    assert value.status.external_operations_enabled is True
