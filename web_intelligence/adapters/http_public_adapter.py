"""Minimal injected public HTTP extraction adapter."""
from collections.abc import Callable
from web_intelligence.enums import AdapterKind
from web_intelligence.exceptions import ResourceLimitError
from web_intelligence.models import AdapterRequest,AdapterResult,AdapterStatus
from web_intelligence.policy import ALLOWED_CONTENT_TYPES
from web_intelligence.url_safety import UrlSafetyValidator

Fetch=Callable[[str,int],tuple[str,str,bytes]]
class HttpPublicAdapter:
    def __init__(self,validator:UrlSafetyValidator,fetcher:Fetch|None=None,maximum_bytes:int=1_000_000):
        self.validator=validator; self.fetcher=fetcher; self.maximum_bytes=maximum_bytes
        self.status=AdapterStatus(kind=AdapterKind.HTTP_PUBLIC,available=fetcher is not None,reason="Injected safe fetcher ready." if fetcher else "No live HTTP fetcher injected.")
    def execute(self,request:AdapterRequest)->AdapterResult:
        if self.fetcher is None: raise ResourceLimitError("HTTP adapter is unavailable.",error_code="ADAPTER_UNAVAILABLE")
        url=self.validator.validate(request.url); final_url,content_type,body=self.fetcher(url,self.maximum_bytes)
        canonical=self.validator.validate_redirect(url,final_url,redirect_count=1,maximum_redirects=3)
        media=content_type.split(";",1)[0].lower()
        if media not in ALLOWED_CONTENT_TYPES: raise ResourceLimitError("Content type is not allowlisted.",error_code="CONTENT_TYPE_BLOCKED")
        if len(body)>self.maximum_bytes: raise ResourceLimitError("Page exceeded byte limit.",error_code="PAGE_TOO_LARGE")
        text=body.decode("utf-8",errors="replace") if media.startswith("text/") or media.endswith("json") else ""
        return AdapterResult(adapter=AdapterKind.HTTP_PUBLIC,canonical_url=canonical,title="Public source",content_type=media,content_bytes=len(body),excerpt=text[:500])
