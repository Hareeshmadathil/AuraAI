"""Provider-independent web adapter contract."""
from typing import Protocol
from web_intelligence.models import AdapterRequest,AdapterResult,AdapterStatus
class WebAdapter(Protocol):
    status:AdapterStatus
    def execute(self,request:AdapterRequest)->AdapterResult: ...
