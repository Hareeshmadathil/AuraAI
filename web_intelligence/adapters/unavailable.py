"""Safe unavailable adapter implementation."""
from web_intelligence.enums import AdapterKind
from web_intelligence.exceptions import WebIntelligenceError
from web_intelligence.models import AdapterRequest,AdapterResult,AdapterStatus
class UnavailableAdapter:
    def __init__(self,kind:AdapterKind,reason:str,version:str|None=None): self.status=AdapterStatus(kind=kind,available=False,reason=reason,version=version)
    def execute(self,request:AdapterRequest)->AdapterResult:
        del request
        raise WebIntelligenceError(self.status.reason,error_code="ADAPTER_UNAVAILABLE")
