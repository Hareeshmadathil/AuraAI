"""Deterministic aliases and canonical text; no embeddings."""
import re
from urllib.parse import urlsplit,urlunsplit
ALIASES={"google gemini":"gemini","nvidia nemotron":"nemotron","youtube":"youtube"}
def normalize_text(value:str)->str: return re.sub(r"\s+"," ",value.strip().casefold())
def normalize_entity(value:str)->str: return ALIASES.get(normalize_text(value),normalize_text(value))
def canonical_claim(value:str)->str: return re.sub(r"[^a-z0-9%.$€£]+"," ",normalize_text(value)).strip()
def normalize_url(value:str)->str:
    parts=urlsplit(value); return urlunsplit((parts.scheme.casefold(),(parts.hostname or "").casefold(),parts.path.rstrip("/") or "/",parts.query,""))
