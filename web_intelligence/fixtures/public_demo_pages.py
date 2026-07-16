"""Deterministic public-page fixtures; no network behavior."""
DEMO_URL="https://example.com/"
DEMO_HTML=b"<html><head><title>Example Domain</title></head><body><p>Reserved example content.</p></body></html>"
def demo_fetcher(url:str,maximum_bytes:int)->tuple[str,str,bytes]:
    assert url==DEMO_URL and len(DEMO_HTML)<=maximum_bytes
    return url,"text/html; charset=utf-8",DEMO_HTML
