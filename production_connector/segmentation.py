"""Deterministic, lossless provider segmentation."""
from __future__ import annotations

import hashlib

from production_connector.models import MissionPackage, ScriptSegment, VisualType

ASSETS = ["early-code", "git-history", "dashboard", "mission-terminal", "roster", "quality-breakdown",
          "subtitle-failure", "subtitle-correction", "test-result", "founder-review", "youtube-profile", "social-profile"]
TITLES = ["Opening hook", "From script to system", "Why roles matter", "Architecture", "Failures and safeguards",
          "Mission Zero workflow", "Honest limits", "What comes next", "Call to action"]
VISUALS = [VisualType.PRESENTER, VisualType.SCREEN_RECORDING, VisualType.MOTION_GRAPHIC,
           VisualType.PRESENTER, VisualType.SCREEN_RECORDING, VisualType.B_ROLL,
           VisualType.PRESENTER, VisualType.MOTION_GRAPHIC, VisualType.PRESENTER]
EVIDENCE = [["dashboard"], ["early-code", "git-history"], ["quality-breakdown"], ["dashboard", "roster"],
            ["subtitle-failure", "subtitle-correction", "test-result", "git-history"],
            ["mission-terminal", "quality-breakdown", "founder-review"], [], ["founder-review"], ["youtube-profile", "social-profile"]]


def segment_script(package: MissionPackage) -> list[ScriptSegment]:
    """Map every source section once, preserving exact text and order."""
    total_words = sum(len(section.split()) for section in package.sections)
    segments = []
    for index, text in enumerate(package.sections):
        visual = VISUALS[index] if index < len(VISUALS) else VisualType.B_ROLL
        evidence = EVIDENCE[index] if index < len(EVIDENCE) else []
        segments.append(ScriptSegment(segment_id=f"segment-{index + 1:02d}", order=index + 1,
            section_title=TITLES[index] if index < len(TITLES) else f"Section {index + 1}", narration_text=text,
            estimated_duration_seconds=round(package.estimated_duration_seconds * len(text.split()) / total_words, 3),
            visual_type=visual, avatar_visible=visual == VisualType.PRESENTER, evidence_required=evidence,
            asset_requirement_ids=evidence, subtitle_references=[f"segment-{index + 1:02d}"],
            transition_notes="Use a restrained cut or evidence-led transition.",
            founder_notes="Capture listed evidence; missing assets must remain clearly marked.",
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(), shorts_candidate=index in {0, 4, 6},
            is_cta=index == len(package.sections) - 1))
    return segments
