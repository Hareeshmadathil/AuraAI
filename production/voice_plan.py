"""Provider-neutral voiceover planning."""

from __future__ import annotations

from core import ValidationError
from production.models import Storyboard, VideoScript, VoiceProfile, VoiceSegment, VoiceoverPlan


class VoicePlanBuilder:
    """Create scene-linked voice performance directions without synthesis."""

    def build(
        self,
        script: VideoScript,
        storyboard: Storyboard,
        *,
        language: str,
        tone: str,
    ) -> VoiceoverPlan:
        """Build a deterministic voice plan from script and storyboard."""

        if not language.strip() or not tone.strip():
            raise ValidationError("Voice language and tone are required.")
        profile = VoiceProfile(
            name="AuraAI Editorial Voice",
            language=language,
            voice_character=f"Clear, grounded, and {tone.strip().lower()}.",
            pace_words_per_minute=140,
            energy_level="measured with purposeful emphasis",
            pronunciation_notes=[
                f"Confirm pronunciation of '{script.primary_keyword}'.",
                "Review acronyms and brand terms before recording.",
            ],
            provider_hint="Future provider supplied through dependency injection only",
            sample_data=script.sample_data,
        )
        segments = [
            VoiceSegment(
                scene_id=scene.scene_id,
                text=scene.narration,
                estimated_duration_seconds=round(
                    scene.end_seconds - scene.start_seconds, 2
                ),
                emotion="curious" if scene.sequence_number == 1 else "confident and helpful",
                emphasis_words=self._emphasis_words(scene.on_screen_text),
                pause_after_seconds=0.6 if scene.sequence_number < len(storyboard.scenes) else 1.0,
                pronunciation_notes=list(profile.pronunciation_notes),
            )
            for scene in storyboard.scenes
        ]
        return VoiceoverPlan(
            script_id=script.script_id,
            profile=profile,
            segments=segments,
            total_duration_seconds=sum(
                segment.estimated_duration_seconds for segment in segments
            ),
            output_format="wav_48khz_mono_planned",
            sample_data=script.sample_data,
        )

    @staticmethod
    def _emphasis_words(text: str) -> list[str]:
        return [word.strip(".,:;!?") for word in text.split()[:3] if word]
