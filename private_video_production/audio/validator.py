"""Validate licensed optional audio and narration-first defaults."""

from core import ValidationError

from private_video_production.models import AudioMixPlan


def validate_audio_mix(plan: AudioMixPlan) -> None:
    """Reject unsupported gain or unlicensed music state."""

    if plan.music_relative_path and not plan.music_license_note:
        raise ValidationError("Background music requires founder-supplied license metadata.")
    if plan.music_gain_db >= -12:
        raise ValidationError("Background music must remain below narration.")
