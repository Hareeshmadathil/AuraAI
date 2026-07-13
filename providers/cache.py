"""Optional deterministic in-memory cache for provider results."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from providers.models import ProviderCapability
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult


def provider_cache_key(
    capability: ProviderCapability,
    prompt: ProviderPrompt,
) -> str:
    """Build a stable hash without persisting or logging prompt content."""

    payload = json.dumps(
        {"capability": capability.value, "prompt": prompt.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class MemoryProviderCache:
    """Process-local cache disabled unless explicitly supplied to a router."""

    def __init__(self) -> None:
        self._values: dict[str, ProviderResult[Any]] = {}

    def get(self, key: str) -> ProviderResult[Any] | None:
        value = self._values.get(key)
        return deepcopy(value) if value is not None else None

    def set(self, key: str, value: ProviderResult[Any]) -> None:
        self._values[key] = deepcopy(value)

    def clear(self) -> None:
        self._values.clear()

    def size(self) -> int:
        return len(self._values)
