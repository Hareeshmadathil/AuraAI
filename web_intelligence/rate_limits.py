"""Per-domain serial request limits."""
from time import monotonic
from web_intelligence.exceptions import ResourceLimitError
class DomainRateLimiter:
    def __init__(self,minimum_delay_seconds:float=2,maximum_requests:int=5,clock=monotonic):
        self.delay=minimum_delay_seconds; self.maximum=maximum_requests; self.clock=clock; self._state:dict[str,tuple[int,float]]={}
    def acquire(self,domain:str)->None:
        count,last=self._state.get(domain,(0,float("-inf"))); now=self.clock()
        if count>=self.maximum: raise ResourceLimitError("Per-domain request limit reached.",error_code="DOMAIN_RATE_LIMIT")
        if now-last<self.delay: raise ResourceLimitError("Minimum domain delay has not elapsed.",error_code="DOMAIN_DELAY")
        self._state[domain]=(count+1,now)
