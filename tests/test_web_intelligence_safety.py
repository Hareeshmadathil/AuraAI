"""URL, robots, approval, rate, and browser-policy safety tests."""
from datetime import timedelta
import pytest
from agents.specialists import TrendHunter
from core import utc_now
from web_intelligence.approvals import ApprovalService
from web_intelligence.enums import BrowserAction
from web_intelligence.exceptions import ApprovalError,ResourceLimitError,RobotsDeniedError,UnsafeUrlError,WebIntelligenceError
from web_intelligence.models import CrawlLimits,WebResearchPlan
from web_intelligence.policy import WebPolicy
from web_intelligence.rate_limits import DomainRateLimiter
from web_intelligence.robots import RobotsPolicy
from web_intelligence.url_safety import UrlSafetyValidator
from web_intelligence.composition import create_offline_demo_service
from runtime_engine import RuntimeEventBus
from runtime_engine.models import RuntimeEventType

def validator(addresses=None): return UrlSafetyValidator(["example.com"],resolver=lambda host:addresses or ["93.184.216.34"])
def test_public_https_and_domain_allowlist():
    assert validator().validate("https://docs.example.com/a#fragment")=="https://docs.example.com/a"
    for url in ("file:///x","ftp://example.com/x","https://user:pass@example.com","https://evil.test","https://example.com:8443"):
        with pytest.raises(UnsafeUrlError): validator().validate(url)
@pytest.mark.parametrize("address",["127.0.0.1","10.0.0.1","172.16.1.1","192.168.1.1","169.254.169.254","::1"])
def test_ssrf_addresses_blocked(address):
    with pytest.raises(UnsafeUrlError): validator([address]).validate("https://example.com")
def test_redirect_revalidates_dns_and_limits():
    answers=iter([["93.184.216.34"],["127.0.0.1"]])
    value=UrlSafetyValidator(["example.com"],resolver=lambda host:next(answers))
    with pytest.raises(UnsafeUrlError): value.validate_redirect("https://example.com","https://example.com/next",redirect_count=1,maximum_redirects=3)
    with pytest.raises(UnsafeUrlError): validator().validate_redirect("https://example.com","https://example.com/x",redirect_count=4,maximum_redirects=3)
def test_robots_and_rate_limits():
    with pytest.raises(RobotsDeniedError): RobotsPolicy(lambda url,agent:False).require_allowed("https://example.com")
    clock=iter([0.0,1.0,3.0]).__next__; limiter=DomainRateLimiter(2,2,clock); limiter.acquire("example.com")
    with pytest.raises(ResourceLimitError): limiter.acquire("example.com")
    limiter.acquire("example.com")
def test_bounded_limit_models_and_browser_actions():
    with pytest.raises(ValueError): CrawlLimits(maximum_pages=6)
    policy=WebPolicy(); policy.validate_browser_action(BrowserAction.SCROLL,known_domain=True)
    with pytest.raises(WebIntelligenceError): policy.validate_browser_action(BrowserAction.CLICK,known_domain=False)
    with pytest.raises(WebIntelligenceError): policy.validate_browser_action(BrowserAction.CLICK,known_domain=True,login_prompt=True)
def test_plan_hash_approval_and_expiry():
    service=ApprovalService(); plan=service.prepare(WebResearchPlan(objective="o",research_question="q",approved_domains=["example.com"],adapter_rationale="public evidence"))
    approved,record=service.approve(plan,founder_confirmed=True); service.require(approved,record)
    with pytest.raises(ApprovalError): service.approve(plan.model_copy(update={"objective":"changed"}),founder_confirmed=True)
    expired=service.prepare(WebResearchPlan(objective="o",research_question="q",approved_domains=["example.com"],adapter_rationale="x",created_at=utc_now()-timedelta(days=2),expires_at=utc_now()-timedelta(days=1)))
    with pytest.raises(ApprovalError): service.approve(expired,founder_confirmed=True)
def test_existing_trend_hunter_is_reused_without_mission_execution():
    service=create_offline_demo_service(); count=len(service.plans)
    plan=service.draft_from_trend_hunter(TrendHunter(),question="What public trend evidence exists?",domains=["example.com"])
    assert len(service.plans)==count+1 and "Trend Hunter" in plan.objective
def test_plan_runtime_event_contains_safe_metadata_only():
    bus=RuntimeEventBus(); service=create_offline_demo_service(); service.event_bus=bus
    plan=service.draft_plan(objective="safe",question="question",domains=["example.com"])
    event=bus.filter_by_type(RuntimeEventType.WEB_RESEARCH_PLAN_CREATED)[0]
    assert event.metadata=={"plan_id":str(plan.plan_id),"domain_count":1,"status":"pending"}
