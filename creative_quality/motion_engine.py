"""Provider-neutral motion and scene-rhythm planning."""

from production.models import Storyboard, VideoStyle

from creative_quality.models import MotionCue, MotionPlan


class MotionEngine:
    """Create one restrained motion cue for every storyboard scene."""

    def analyze(self, storyboard: Storyboard) -> MotionPlan:
        cues: list[MotionCue] = []
        overload: list[str] = []
        for scene in storyboard.scenes:
            duration = scene.end_seconds - scene.start_seconds
            style = self._motion_type(scene.style)
            intensity = "low" if duration < 4 else "moderate"
            if duration < 2.5:
                overload.append(
                    f"Scene {scene.sequence_number} is too brief for layered motion."
                )
            cues.append(
                MotionCue(
                    scene_id=scene.scene_id,
                    start_seconds=scene.start_seconds,
                    end_seconds=scene.end_seconds,
                    motion_type=style,
                    purpose="Direct attention to the scene's single explanatory idea.",
                    intensity=intensity,
                    instructions=(
                        "Use one eased entrance, hold long enough to read, and avoid "
                        "continuous decorative motion."
                    ),
                    accessibility_notes=(
                        "Respect reduced-motion preferences and preserve text contrast."
                    ),
                )
            )
        rhythm = max(60.0, 90.0 - len(overload) * 8)
        return MotionPlan(
            storyboard_id=storyboard.storyboard_id,
            cues=cues,
            transition_strategy=(
                "Use cuts for idea changes and short dissolves only for "
                "reflective beats."
            ),
            kinetic_typography_strategy=(
                "Animate only one verified keyword or number at a time."
            ),
            infographic_strategy=(
                "Reveal comparisons progressively; label assumptions and sources."
            ),
            visual_rhythm_score=rhythm,
            overload_risks=overload,
        )

    @staticmethod
    def _motion_type(style: VideoStyle) -> str:
        return {
            VideoStyle.DOCUMENTARY: "documentary pan and evidence callout",
            VideoStyle.MOTION_GRAPHICS: "restrained shape and typography reveal",
            VideoStyle.ANIME: "anime preview parallax",
            VideoStyle.CINEMATIC_LIVE_ACTION: "cinematic preview push-in",
            VideoStyle.HYBRID: "hybrid footage and graphic emphasis",
        }.get(style, "subtle scene emphasis")
