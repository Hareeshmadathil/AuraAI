"""Injected robots.txt decisions; deny on uncertainty."""
from collections.abc import Callable
from web_intelligence.exceptions import RobotsDeniedError

class RobotsPolicy:
    def __init__(self,checker:Callable[[str,str],bool]|None=None,user_agent:str="AuraAI-WebIntelligence/1.0 (+founder-controlled)"):
        self.checker=checker; self.user_agent=user_agent
    def require_allowed(self,url:str)->None:
        if self.checker is None: raise RobotsDeniedError("Robots status is unavailable; crawl denied.",error_code="ROBOTS_UNAVAILABLE")
        if not self.checker(url,self.user_agent): raise RobotsDeniedError("robots.txt denied this URL.",error_code="ROBOTS_DENIED")
