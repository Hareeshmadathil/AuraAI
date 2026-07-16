"""Public web adapter contracts and optional factories."""
from web_intelligence.adapters.base import WebAdapter
from web_intelligence.adapters.browser_use_adapter import create_browser_use_adapter
from web_intelligence.adapters.crawl4ai_adapter import (
    InstalledCrawl4AIAdapter,
    create_crawl4ai_adapter,
)
from web_intelligence.adapters.http_public_adapter import HttpPublicAdapter
from web_intelligence.adapters.unavailable import UnavailableAdapter
__all__=["HttpPublicAdapter","InstalledCrawl4AIAdapter","UnavailableAdapter","WebAdapter","create_browser_use_adapter","create_crawl4ai_adapter"]
