"""Storyboard generation from deterministic scripts."""

from __future__ import annotations

from production.models import ContentBrief, Storyboard, StoryboardScene, VideoScript


class StoryboardEngine:
    """Translate every script section into a sequential visual scene."""

    def build(self, script: VideoScript, brief: ContentBrief) -> Storyboard:
        """Build safe, provider-neutral visual directions."""

        scenes: list[StoryboardScene] = []
        cursor = 0.0
        shot_types = ("wide establishing", "medium presenter", "graphic close-up")
        for sequence, section in enumerate(script.sections, start=1):
            end = round(cursor + section.estimated_duration_seconds, 2)
            on_screen = section.title if len(section.title) <= 48 else section.title[:45] + "..."
            scenes.append(
                StoryboardScene(
                    sequence_number=sequence,
                    script_section_id=section.section_id,
                    start_seconds=cursor,
                    end_seconds=end,
                    narration=section.narration,
                    visual_description=(
                        f"Original {brief.selected_style.value.replace('_', ' ')} scene "
                        f"illustrating {section.title.lower()} with simple, legible evidence "
                        "labels and no simulated final footage claim."
                    ),
                    style=brief.selected_style,
                    shot_type=shot_types[(sequence - 1) % len(shot_types)],
                    camera_direction="Use restrained movement and hold long enough to read.",
                    on_screen_text=on_screen,
                    transition="clean cut" if sequence == 1 else "short cross dissolve",
                    visual_prompt=(
                        f"Create an original, provider-neutral {brief.selected_style.value} "
                        f"visual for '{section.title}', professional educational composition, "
                        "high contrast, no text baked into the image"
                    ),
                    negative_prompt=(
                        "copyrighted characters, living artist imitation, unauthorized logos, "
                        "watermarks, misleading statistics, distorted text"
                    ),
                    source_asset_requirements=[
                        "Use original or properly licensed source assets.",
                        "Verify any depicted product or interface rights.",
                    ],
                    safety_notes=[
                        "Do not imitate copyrighted characters or living artists.",
                        "Treat this as a planned prompt, not a generated asset.",
                    ],
                )
            )
            cursor = end
        return Storyboard(
            script_id=script.script_id,
            scenes=scenes,
            total_duration_seconds=cursor,
            style_continuity_notes=[
                f"Keep the {brief.selected_style.value} palette and lighting consistent.",
                "Use one typography system only during future assembly.",
            ],
            character_continuity_notes=[
                "Use no recurring person unless an authorized reference is supplied.",
                "Keep recurring objects, colors, and scale consistent across scenes.",
            ],
            sample_data=script.sample_data,
        )
