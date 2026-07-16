"""Bounded crawl and browser policies."""
from web_intelligence.enums import BrowserAction,OperatingMode
from web_intelligence.exceptions import WebIntelligenceError
from web_intelligence.models import CrawlLimits

PROHIBITED_ACTIONS=("login","submit_form","download","upload","purchase","message","post","account_creation","accept_terms")
ALLOWED_CONTENT_TYPES=frozenset({"text/html","text/plain","text/xml","application/xml","application/json","application/pdf"})
class WebPolicy:
    def __init__(self,mode:OperatingMode=OperatingMode.OFFLINE,limits:CrawlLimits|None=None): self.mode=mode; self.limits=limits or CrawlLimits()
    def require_execution_mode(self)->None:
        if self.mode==OperatingMode.OFFLINE: raise WebIntelligenceError("Web execution is disabled in OFFLINE mode.",error_code="WEB_OFFLINE")
        if self.mode==OperatingMode.FOUNDER_APPROVED_ACTION: raise WebIntelligenceError("Founder-approved actions are architecture-only in V1.",error_code="ACTION_MODE_DISABLED")
    def validate_browser_action(self,action:BrowserAction,*,known_domain:bool,login_prompt:bool=False)->None:
        if action not in set(BrowserAction): raise WebIntelligenceError("Browser action is not allowlisted.",error_code="BROWSER_ACTION_BLOCKED")
        if not known_domain: raise WebIntelligenceError("Unexpected domain requires founder approval.",error_code="UNKNOWN_DOMAIN")
        if login_prompt: raise WebIntelligenceError("Browser stopped at a login prompt.",error_code="LOGIN_BLOCKED")
