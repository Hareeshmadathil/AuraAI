"""Bounded HTTP body decoding with content-free structural diagnostics."""
from __future__ import annotations
import json
import re
import zlib
from collections.abc import Mapping
from typing import Any
from providers.exceptions import ProviderValidationError

_CHARSET = re.compile(r"charset=([A-Za-z0-9._-]+)", re.IGNORECASE)
_SAFE_HEADERS = frozenset({"content-type", "content-encoding", "transfer-encoding",
                           "content-length", "x-request-id", "request-id", "nvcf-reqid"})


def _error(code: str, message: str, diagnostics: dict[str, Any]) -> ProviderValidationError:
    return ProviderValidationError(message, provider_name="nemotron",
        details={"safe_error_code": code, "validation_stage": "http_body_decoding",
                 "transport_completed": True, **diagnostics}, retryable=False)


class NemotronHttpDecoder:
    """Decode only supported text/JSON HTTP bodies without exposing content."""
    def __init__(self, maximum_response_bytes: int = 2_000_000) -> None:
        self.maximum_response_bytes = maximum_response_bytes

    def decode(self, body: bytes | str, headers: Mapping[str, str], *, status: int) -> tuple[dict[str, Any], dict[str, Any]]:
        safe_headers = self.safe_headers(headers)
        raw = body.encode("utf-8") if isinstance(body, str) else body
        diagnostics: dict[str, Any] = {"http_status":status,"http_status_class":f"{status//100}xx",
            "safe_response_headers":safe_headers,"response_byte_count":len(raw),"body_value_type":type(body).__name__,
            "first_byte_classification":self.classify(raw),"text_decoding":"not_started","json_decoder_succeeded":False}
        if not raw: raise _error("EMPTY_FINAL_ANSWER", "Nemotron returned an empty HTTP body.", diagnostics)
        if len(raw)>self.maximum_response_bytes: raise _error("MALFORMED_PROVIDER_RESPONSE", "Nemotron response exceeded the safe size limit.", diagnostics)
        encoding=safe_headers.get("content-encoding","").lower()
        try:
            if encoding=="gzip" or raw.startswith(b"\x1f\x8b"): raw=self._decompress(raw,16+zlib.MAX_WBITS)
            elif encoding=="deflate": raw=self._decompress(raw,zlib.MAX_WBITS)
            elif encoding not in {"","identity"}: raise _error("UNSUPPORTED_CONTENT_ENCODING", "Nemotron used an unsupported content encoding.", diagnostics)
        except (zlib.error,EOFError):
            raise _error("MALFORMED_PROVIDER_RESPONSE", "Nemotron returned invalid compressed data.", diagnostics) from None
        if len(raw)>self.maximum_response_bytes: raise _error("MALFORMED_PROVIDER_RESPONSE", "Nemotron decompressed response exceeded the safe size limit.", diagnostics)
        classification=self.classify(raw)
        if classification=="HTML prefix": raise _error("HTML_RESPONSE_REJECTED", "Nemotron returned an HTML response.", diagnostics)
        if classification=="SSE prefix": raise _error("SSE_RESPONSE_REJECTED", "Nemotron returned SSE despite non-streaming mode.", diagnostics)
        charset=self._charset(safe_headers.get("content-type",""))
        try: text=raw.decode(charset).removeprefix("\ufeff")
        except (UnicodeError,LookupError): raise _error("MALFORMED_PROVIDER_RESPONSE", "Nemotron response text decoding failed.", diagnostics) from None
        diagnostics["text_decoding"]=charset
        try:
            decoded: object=json.loads(text)
            if isinstance(decoded,str): decoded=json.loads(decoded)
        except json.JSONDecodeError as error:
            diagnostics["json_decode_error_position"]=error.pos
            diagnostics["json_decode_error_category"]=error.__class__.__name__
            raise _error("MALFORMED_PROVIDER_RESPONSE", "Nemotron response was not a valid JSON envelope.", diagnostics) from None
        if not isinstance(decoded,dict):
            diagnostics["parsed_top_level_type"]=type(decoded).__name__
            raise _error("MALFORMED_PROVIDER_RESPONSE", "Nemotron response envelope was not a JSON object.", diagnostics)
        diagnostics.update(json_decoder_succeeded=True,parsed_top_level_type="dict",parsed_top_level_keys=sorted(decoded))
        return decoded,diagnostics

    @staticmethod
    def safe_headers(headers: Mapping[str,str]) -> dict[str,str]:
        return {str(key).lower():str(value)[:200] for key,value in headers.items() if str(key).lower() in _SAFE_HEADERS}

    @staticmethod
    def classify(raw: bytes) -> str:
        stripped=raw.lstrip()
        if raw.startswith(b"\x1f\x8b"): return "gzip magic"
        if raw.startswith(b"\xef\xbb\xbf"): return "UTF-8 BOM"
        if stripped.startswith(b"{"): return "JSON object"
        if stripped.startswith(b"["): return "JSON array"
        if stripped.startswith((b"data:",b"event:")): return "SSE prefix"
        if stripped.lower().startswith((b"<!doctype html",b"<html")): return "HTML prefix"
        return "unknown"

    @staticmethod
    def _charset(content_type: str) -> str:
        match=_CHARSET.search(content_type)
        return match.group(1).lower() if match else "utf-8-sig"

    def _decompress(self, raw: bytes, window_bits: int) -> bytes:
        decoder=zlib.decompressobj(window_bits)
        value=decoder.decompress(raw,self.maximum_response_bytes+1)
        if len(value)>self.maximum_response_bytes or decoder.unconsumed_tail:
            raise EOFError("bounded decompression limit exceeded")
        value+=decoder.flush(self.maximum_response_bytes+1-len(value))
        if len(value)>self.maximum_response_bytes or not decoder.eof:
            raise EOFError("bounded decompression failed")
        return value
