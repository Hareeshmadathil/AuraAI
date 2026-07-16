"""Offline ElevenLabs preparation exporter."""
from production_connector.exporter import PackageWriter
from production_connector.models import MissionPackage, ScriptSegment

TERMS = ["AuraAI", "Gemini", "Pydantic", "FFmpeg", "GitHub", "Mission Zero", "Python", "API", "SEO"]

def export(writer: PackageWriter, package: MissionPackage, segments: list[ScriptSegment]) -> None:
    base = "provider-packages/elevenlabs/"
    writer.text(base + "narration-full.txt", "\n\n".join(s.narration_text for s in segments))
    data = [s.model_dump(mode="json") for s in segments]
    writer.json(base + "narration-segments.json", data)
    writer.text(base + "narration-segments.md", "# Narration segments\n\n" + "\n\n".join(f"## {s.segment_id}: {s.section_title}\n\n{s.narration_text}" for s in segments))
    writer.json(base + "pronunciation-dictionary.json", {"provider_action_performed": False, "entries": [{"term": t, "pronunciation": "Founder must review and supply phonetic spelling"} for t in TERMS]})
    writer.json(base + "generation-settings.json", {"recommendations_only": True, "voice_id": None, "api_key": None, "stability": "evaluate with a short test", "similarity": "evaluate with a short test", "rights_pricing_quotas": "Founder verification required"})
    writer.text(base + "voice-evaluation-scorecard.md", "# Voice evaluation scorecard\n\nScore clarity, warmth, pacing, pronunciation, consistency, and brand fit. Voice generation is not approved by package export.")
    writer.text(base + "upload-checklist.md", "# Manual upload checklist\n\n- [ ] Founder approves voice generation independently\n- [ ] Select voice manually\n- [ ] Verify current rights, pricing, and quotas\n- [ ] Remove secrets from screen captures\n- [ ] Generate nothing until approved")
