"""Dependency-injected transport boundary for NVIDIA Nemotron."""
from __future__ import annotations
from collections.abc import Callable
from typing import Protocol
from providers.exceptions import ProviderUnavailableError
from providers.nemotron.models import NemotronRequest, NemotronTransportResponse


class NemotronTransport(Protocol):
    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse: ...


class MockNemotronTransport:
    """In-memory transport used by tests; never performs I/O."""
    def __init__(self, responder: Callable[[NemotronRequest], NemotronTransportResponse]) -> None:
        self._responder = responder
        self.requests: list[NemotronRequest] = []
        self.timeouts: list[float] = []

    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse:
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        return self._responder(request)


class UnavailableNemotronTransport:
    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse:
        del request, timeout_seconds
        raise ProviderUnavailableError("No Nemotron transport was explicitly configured.", provider_name="nemotron", retryable=False)
