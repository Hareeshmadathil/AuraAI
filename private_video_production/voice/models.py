"""Voice-specific models and deterministic pronunciation defaults."""

from private_video_production.models import (
    NarrationSegment,
    VoiceProfile,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
)

PRONUNCIATION_OVERRIDES = {
    "AuraAI": "Aura A I",
    "Gemini": "Gem in eye",
    "Pydantic": "pie dan tick",
    "FFmpeg": "F F m peg",
    "Python": "Pie thon",
    "GitHub": "Git Hub",
    "Mission Zero": "Mission Zero",
}

__all__ = [
    "NarrationSegment",
    "PRONUNCIATION_OVERRIDES",
    "VoiceProfile",
    "VoiceSynthesisRequest",
    "VoiceSynthesisResult",
]
