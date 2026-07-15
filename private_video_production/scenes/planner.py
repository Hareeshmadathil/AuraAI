"""Deterministic documentary scene planning over the approved script."""

from __future__ import annotations

import math

from private_video_production.models import (
    AssetRequirement,
    AssetType,
    PrivateVideoProductionInput,
    SceneEvidenceReference,
    ScenePlan,
    SceneVisual,
    VisualType,
)
from private_video_production.scenes.evidence import matching_evidence


class MissionZeroScenePlanner:
    """Map every narration section to purposeful 3–8 second visuals."""

    _VISUAL_CYCLE = (
        VisualType.SCREEN_RECORDING,
        VisualType.MOTION_GRAPHIC,
        VisualType.SCREENSHOT,
        VisualType.MOTION_GRAPHIC,
        VisualType.DIAGRAM,
        VisualType.SCREEN_RECORDING,
        VisualType.PLACEHOLDER,
        VisualType.TYPOGRAPHY,
        VisualType.SCREEN_RECORDING,
        VisualType.MOTION_GRAPHIC,
    )

    def plan(
        self,
        production_input: PrivateVideoProductionInput,
    ) -> tuple[list[ScenePlan], list[AssetRequirement]]:
        """Create complete coverage and concrete founder capture requirements."""

        scenes: list[ScenePlan] = []
        requirements: dict[str, AssetRequirement] = {}
        cursor = 0.0
        headings = (
            "The harder problem", "The first simple version",
            "Why one script was insufficient", "Building the company structure",
            "Failures that changed the system", "Mission Zero working today",
            "What still does not work", "What comes next", "Follow the build in public",
        )
        total_words = sum(len(section.split()) for section in production_input.sections)
        for section_index, text in enumerate(production_input.sections, start=1):
            heading = headings[section_index - 1] if section_index <= len(headings) else f"Section {section_index}"
            duration = production_input.estimated_duration_seconds * len(text.split()) / total_words
            scene_count = max(1, math.ceil(duration / 6.5))
            scene_duration = duration / scene_count
            evidence = matching_evidence(f"{heading} {text}")
            for local_index in range(scene_count):
                sequence = len(scenes) + 1
                visual_type = self._VISUAL_CYCLE[(sequence - 1) % len(self._VISUAL_CYCLE)]
                start = cursor + local_index * scene_duration
                end = cursor + (local_index + 1) * scene_duration
                scene_id = f"scene-{sequence:03d}"
                evidence_item = evidence[local_index % len(evidence)] if evidence else None
                required_asset_ids: list[str] = []
                founder_capture = visual_type in {
                    VisualType.SCREEN_RECORDING,
                    VisualType.SCREENSHOT,
                    VisualType.FOUNDER_IMAGE,
                }
                references: list[SceneEvidenceReference] = []
                if evidence_item:
                    asset_id = evidence_item["id"]
                    references.append(
                        SceneEvidenceReference(
                            reference_id=asset_id,
                            description=evidence_item["label"],
                            verified=False,
                        )
                    )
                    required_asset_ids.append(asset_id)
                    founder_capture = True
                    requirements.setdefault(
                        asset_id,
                        self._requirement(asset_id, evidence_item["label"], scene_id),
                    )
                    existing = requirements[asset_id]
                    if scene_id not in existing.scene_ids:
                        existing.scene_ids.append(scene_id)
                if founder_capture and not required_asset_ids:
                    asset_id = f"capture-{section_index:02d}"
                    required_asset_ids.append(asset_id)
                    requirements.setdefault(
                        asset_id,
                        self._requirement(asset_id, f"Visual evidence for {heading}", scene_id),
                    )
                    existing = requirements[asset_id]
                    if scene_id not in existing.scene_ids:
                        existing.scene_ids.append(scene_id)
                actual_type = VisualType.PLACEHOLDER if founder_capture else visual_type
                scenes.append(
                    ScenePlan(
                        scene_id=scene_id,
                        narration_segment_id=f"section-{section_index:02d}",
                        expected_start_seconds=round(start, 3),
                        expected_end_seconds=round(end, 3),
                        visual=SceneVisual(
                            visual_type=actual_type,
                            purpose=(
                                f"Show {evidence_item['label']} beside the relevant claim."
                                if evidence_item
                                else f"Support the viewer question: {heading}."
                            ),
                            on_screen_text=heading[:120],
                            camera_instruction="Use restrained parallax or a slow 3% push-in.",
                            transition="short dissolve",
                            placeholder_watermark=(
                                "INTERNAL DRAFT — PLACEHOLDER"
                                if actual_type == VisualType.PLACEHOLDER
                                else None
                            ),
                        ),
                        required_asset_ids=required_asset_ids,
                        evidence_references=references,
                        fallback_visual="Use a branded evidence-needed card; never fabricate a screenshot.",
                        founder_capture_required=founder_capture,
                        accessibility_notes="Keep key text inside title-safe margins with readable contrast.",
                    )
                )
            cursor += duration
        final_scene = scenes[-1]
        scenes[-1] = final_scene.model_copy(
            update={
                "visual": SceneVisual(
                    visual_type=VisualType.TYPOGRAPHY,
                    purpose="End on the mandatory private founder-review boundary.",
                    on_screen_text="PRIVATE DRAFT — FOUNDER REVIEW REQUIRED — NOT PUBLISHED",
                    camera_instruction="Hold the final card steady for legibility.",
                    transition="fade to black",
                ),
                "required_asset_ids": [],
                "evidence_references": [],
                "founder_capture_required": False,
                "fallback_visual": "The mandatory branded private-review final card.",
            }
        )
        return scenes, list(requirements.values())

    @staticmethod
    def _requirement(asset_id: str, description: str, scene_id: str) -> AssetRequirement:
        extension = ".png" if "screenshot" in description.casefold() else ".mp4"
        asset_type = AssetType.IMAGE if extension == ".png" else AssetType.VIDEO
        return AssetRequirement(
            asset_id=asset_id,
            asset_type=asset_type,
            description=description,
            target_relative_path=f"founder-assets/{asset_id}{extension}",
            scene_ids=[scene_id],
            expected_duration_seconds=8 if asset_type == AssetType.VIDEO else None,
            capture_instructions=(
                f"Open the local {description} view, hide private information, and capture only the relevant evidence."
            ),
            privacy_notes=[
                "Hide API keys and .env files.",
                "Hide personal email, recovery codes, notifications, and unrelated files.",
            ],
        )
