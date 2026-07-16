"""Deduplicated founder-approved public source registry."""
from urllib.parse import urlparse
from web_intelligence.url_safety import UrlSafetyValidator
class SourceRegistry:
    def __init__(self,validator:UrlSafetyValidator): self.validator=validator; self._urls:dict[str,str]={}
    def register(self,url:str)->str:
        canonical=self.validator.validate(url); self._urls.setdefault(canonical,canonical); return canonical
    def values(self)->tuple[str,...]: return tuple(self._urls.values())
    @staticmethod
    def domain(url:str)->str: return (urlparse(url).hostname or "").lower()
