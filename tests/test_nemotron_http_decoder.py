"""Transport-body compatibility tests without network calls."""
from __future__ import annotations
import gzip
import json
import pytest
from providers.exceptions import ProviderValidationError
from providers.nemotron import NemotronHttpDecoder

ENVELOPE={"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}],"usage":{}}


@pytest.mark.parametrize("body,headers", [
    (json.dumps(ENVELOPE).encode(), {"content-type":"application/json"}),
    ("\ufeff"+json.dumps(ENVELOPE), {"content-type":"application/json"}),
    (json.dumps(ENVELOPE).encode("utf-16"), {"content-type":"application/json; charset=utf-16"}),
    (gzip.compress(json.dumps(ENVELOPE).encode()), {"content-encoding":"gzip"}),
    (json.dumps(json.dumps(ENVELOPE)).encode(), {"content-type":"application/json"}),
])
def test_supported_http_bodies(body,headers) -> None:
    decoded,diagnostics=NemotronHttpDecoder().decode(body,headers,status=200)
    assert decoded==ENVELOPE and diagnostics["json_decoder_succeeded"]


@pytest.mark.parametrize("body,code", [
    (b"<html>error</html>","HTML_RESPONSE_REJECTED"),
    (b"data: {}\n\n","SSE_RESPONSE_REJECTED"),
    (b"","EMPTY_FINAL_ANSWER"),
    (b'{"bad":',"MALFORMED_PROVIDER_RESPONSE"),
])
def test_unsafe_or_invalid_bodies_are_rejected(body,code) -> None:
    with pytest.raises(ProviderValidationError) as captured:
        NemotronHttpDecoder().decode(body,{"content-type":"application/json"},status=200)
    assert captured.value.details["safe_error_code"]==code
    assert not body or body.decode("utf-8",errors="ignore") not in str(captured.value)


def test_safe_headers_and_size_bound() -> None:
    headers=NemotronHttpDecoder.safe_headers({"Content-Type":"application/json","Authorization":"secret","X-Request-ID":"safe-id"})
    assert headers=={"content-type":"application/json","x-request-id":"safe-id"}
    with pytest.raises(ProviderValidationError):
        NemotronHttpDecoder(maximum_response_bytes=2).decode(b"{}x",{},status=200)
    compressed=gzip.compress(b"x"*1000)
    with pytest.raises(ProviderValidationError):
        NemotronHttpDecoder(maximum_response_bytes=100).decode(compressed,{"content-encoding":"gzip"},status=200)
