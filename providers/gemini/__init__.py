"""Public Gemini stub interfaces."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from providers.gemini.provider import GeminiProvider

from providers.gemini.config import GeminiConfig
from providers.gemini.models import (
    GeminiParserStage,
    GeminiRequest,
    GeminiSafeDiagnostic,
    GeminiSafetyResult,
    GeminiTransportResponse,
    GeminiValidationStage,
    GeminiValidatedResponse,
)
from providers.gemini.prompt_builder import GeminiPromptBuilder
from providers.gemini.response_parser import GeminiResponseParser
from providers.gemini.safety import GeminiSafetyConfig, GeminiSafetyMode
from providers.gemini.transport import (
    GeminiTransport,
    HttpGeminiTransport,
    MockGeminiTransport,
    UnavailableGeminiTransport,
)

__all__ = [
    "GeminiConfig",
    "GeminiParserStage",
    "GeminiRequest",
    "GeminiSafeDiagnostic",
    "GeminiPromptBuilder",
    "GeminiProvider",
    "GeminiResponseParser",
    "GeminiSafetyConfig",
    "GeminiSafetyMode",
    "GeminiSafetyResult",
    "GeminiTransport",
    "GeminiTransportResponse",
    "GeminiValidationStage",
    "GeminiValidatedResponse",
    "HttpGeminiTransport",
    "MockGeminiTransport",
    "UnavailableGeminiTransport",
]


def __getattr__(name: str) -> Any:
    """Load the executable provider module only when explicitly requested."""

    if name == "GeminiProvider":
        from providers.gemini.provider import GeminiProvider

        return GeminiProvider
    raise AttributeError(name)
