"""Offline and injected composition roots."""
from web_intelligence.adapters import HttpPublicAdapter,create_browser_use_adapter,create_crawl4ai_adapter
from web_intelligence.enums import AdapterKind,OperatingMode
from web_intelligence.fixtures.public_demo_pages import demo_fetcher
from web_intelligence.policy import WebPolicy
from web_intelligence.robots import RobotsPolicy
from web_intelligence.service import WebIntelligenceService
from web_intelligence.url_safety import UrlSafetyValidator

def create_offline_demo_service()->WebIntelligenceService:
    resolver=lambda host:["93.184.216.34"]
    validator=UrlSafetyValidator(["example.com"],resolver=resolver)
    adapters={AdapterKind.HTTP_PUBLIC:HttpPublicAdapter(validator,demo_fetcher),AdapterKind.CRAWL4AI:create_crawl4ai_adapter(),AdapterKind.BROWSER_USE:create_browser_use_adapter()}
    service=WebIntelligenceService(policy=WebPolicy(OperatingMode.OFFLINE),adapters=adapters,robots=RobotsPolicy(lambda url,agent:True))
    service.draft_plan(objective="Demonstrate founder-controlled public research without browsing.",question="What is the reserved example domain?",domains=["example.com"],expected_sources=["https://example.com/"])
    return service
