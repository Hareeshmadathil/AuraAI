"""HTTPS, domain, DNS, and redirect safety checks."""
from __future__ import annotations
import ipaddress,socket
from collections.abc import Callable
from urllib.parse import urlparse,urlunparse
from web_intelligence.exceptions import UnsafeUrlError

Resolver=Callable[[str],list[str]]
BLOCKED_HOSTS=frozenset({"metadata.google.internal","169.254.169.254"})
class UrlSafetyValidator:
    def __init__(self,approved_domains:list[str],*,resolver:Resolver|None=None,allow_test_localhost:bool=False):
        self.approved=frozenset(value.lower().rstrip(".") for value in approved_domains); self.resolver=resolver or self._resolve; self.allow_test_localhost=allow_test_localhost
    def validate(self,url:str)->str:
        parsed=urlparse(url)
        if parsed.scheme not in ({"https","http"} if self.allow_test_localhost else {"https"}): self._fail("Only approved HTTPS URLs are allowed.","UNSAFE_SCHEME")
        if parsed.username or parsed.password: self._fail("Embedded URL credentials are forbidden.","EMBEDDED_CREDENTIALS")
        host=(parsed.hostname or "").lower().rstrip(".")
        if not host or any(ord(char)>127 for char in host): self._fail("Hostname is missing or uses unsupported mixed-script characters.","UNSAFE_HOSTNAME")
        if parsed.port not in {None,443} and not (self.allow_test_localhost and parsed.port): self._fail("URL port is not allowlisted.","UNSAFE_PORT")
        if host in BLOCKED_HOSTS or not any(host==domain or host.endswith("."+domain) for domain in self.approved): self._fail("Domain is not founder-approved.","DOMAIN_NOT_APPROVED")
        addresses=self.resolver(host)
        if not addresses: self._fail("DNS did not return a safe address.","DNS_UNAVAILABLE")
        for value in addresses:
            address=ipaddress.ip_address(value)
            if not address.is_global and not (self.allow_test_localhost and address.is_loopback): self._fail("Resolved address is private, local, reserved, or link-local.","SSRF_BLOCKED")
        clean=parsed._replace(fragment="")
        return urlunparse(clean)
    def validate_redirect(self,source:str,target:str,*,redirect_count:int,maximum_redirects:int)->str:
        if redirect_count>maximum_redirects: self._fail("Redirect limit exceeded.","REDIRECT_LIMIT")
        self.validate(source)
        return self.validate(target)
    @staticmethod
    def _resolve(host:str)->list[str]:
        return sorted({item[4][0] for item in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    @staticmethod
    def _fail(message:str,code:str): raise UnsafeUrlError(message,error_code=code)
