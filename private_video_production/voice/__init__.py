"""Provider-neutral local voice synthesis."""

from private_video_production.voice.service import VoiceSynthesisService
from private_video_production.voice.unavailable import UnavailableVoiceAdapter
from private_video_production.voice.windows_sapi import WindowsSapiAdapter

__all__ = ["UnavailableVoiceAdapter", "VoiceSynthesisService", "WindowsSapiAdapter"]
