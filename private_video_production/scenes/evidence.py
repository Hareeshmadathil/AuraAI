"""Verified Mission Zero evidence opportunities and capture guidance."""

from __future__ import annotations


EVIDENCE_OPPORTUNITIES: tuple[dict[str, str], ...] = (
    {"id": "early-code", "keyword": "transcript", "label": "Early transcript-processing code"},
    {"id": "git-history", "keyword": "Git history", "label": "Relevant Git history"},
    {"id": "dashboard", "keyword": "dashboard", "label": "AuraAI dashboard"},
    {"id": "mission-terminal", "keyword": "Mission Manager", "label": "Mission execution terminal"},
    {"id": "roster", "keyword": "CEO", "label": "Employee and company roster"},
    {"id": "quality-breakdown", "keyword": "Creative Quality", "label": "Creative Quality breakdown"},
    {"id": "subtitle-failure", "keyword": "forty-three", "label": "43-character subtitle failure"},
    {"id": "subtitle-correction", "keyword": "wrapped subtitle", "label": "Corrected subtitle behavior"},
    {"id": "test-result", "keyword": "passing tests", "label": "Automated test result"},
    {"id": "founder-gate", "keyword": "stops before publishing", "label": "Mission Zero founder gate"},
    {"id": "social-profiles", "keyword": "subscribe", "label": "Founder-supplied public social profiles"},
)


def matching_evidence(text: str) -> list[dict[str, str]]:
    """Return deterministic evidence matches for narration text."""

    lowered = text.casefold()
    return [item for item in EVIDENCE_OPPORTUNITIES if item["keyword"].casefold() in lowered]
