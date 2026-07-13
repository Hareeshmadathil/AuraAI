"""Deterministic thumbnail concept planning."""

from __future__ import annotations

from production.models import ContentBrief, ThumbnailConcept, ThumbnailPlan, VideoScript


class ThumbnailPlanBuilder:
    """Create distinct, mobile-readable thumbnail directions."""

    def build(self, script: VideoScript, brief: ContentBrief) -> ThumbnailPlan:
        """Build three truthful concepts and select one for testing."""

        keyword = script.primary_keyword
        concepts = [
            self._concept(
                script,
                "Problem to Process",
                "BEFORE → SYSTEM",
                "Split composition: cluttered workflow on the left, clear three-step "
                "process on the right, with one original subject between them.",
                "Relief and practical control",
                "A direct transformation frame should communicate utility at small size.",
            ),
            self._concept(
                script,
                "Three-Step Map",
                "3 SAFE STEPS",
                "Large three-node workflow diagram with a human review checkpoint "
                "highlighted in the center.",
                "Clarity and achievable progress",
                "A numbered framework should attract viewers seeking an actionable guide.",
            ),
            self._concept(
                script,
                "The Review Checkpoint",
                "DON'T SKIP THIS",
                "One bold review gate between an input card and an output card; no "
                "brand logos, income symbols, or fabricated interface screenshots.",
                "Responsible curiosity",
                "A caution-led concept can differentiate the video without misleading fear.",
            ),
        ]
        return ThumbnailPlan(
            script_id=script.script_id,
            concepts=concepts,
            recommended_concept_id=concepts[0].concept_id,
            testing_hypothesis=(
                f"Test 'Problem to Process' first because it makes the benefit of "
                f"{keyword} understandable without promising a result. Compare click "
                "quality and early retention; do not optimize for clicks alone."
            ),
            sample_data=brief.production_input.sample_data,
        )

    @staticmethod
    def _concept(
        script: VideoScript,
        name: str,
        primary_text: str,
        composition: str,
        trigger: str,
        response: str,
    ) -> ThumbnailConcept:
        return ThumbnailConcept(
            title=script.title,
            concept_name=name,
            visual_composition=composition,
            primary_text=primary_text,
            secondary_text=None,
            emotional_trigger=trigger,
            subject_focus="An original, non-celebrity small-business operator or clean diagram.",
            background_direction="Dark uncluttered field with one contextual accent layer.",
            contrast_guidance="Use high luminance contrast and one accent color.",
            mobile_readability_notes="Keep primary text to four words or fewer and test at 10% size.",
            generation_prompt=(
                f"Original YouTube thumbnail concept for '{script.title}': {composition} "
                "high contrast, generous negative space, no baked-in text"
            ),
            negative_prompt=(
                "misleading money symbols, fake metrics, unauthorized logos, copyrighted "
                "characters, celebrity likenesses, living artist imitation, watermarks"
            ),
            expected_audience_response=response,
            sample_data=script.sample_data,
        )
