"""Offline HeyGen scene preparation exporter."""
from production_connector.exporter import PackageWriter
from production_connector.models import MissionPackage, ScriptSegment

def export(writer: PackageWriter, package: MissionPackage, segments: list[ScriptSegment]) -> None:
    base = "provider-packages/heygen/"; scenes = [s.model_dump(mode="json") for s in segments if s.avatar_visible]
    writer.json(base + "avatar-scenes.json", {"candidate": "Terry", "candidate_status": "founder-selected candidate; not permanently approved", "avatar_generation_approved": False, "scenes": scenes})
    writer.text(base + "avatar-scenes.md", "# Avatar scenes\n\nTerry is a founder-selected candidate, not an approval. Use only for hook, transitions, one recap, and CTA. The full video is not a continuous talking head.\n\n" + "\n".join(f"- {s.segment_id}: {s.section_title}" for s in segments if s.avatar_visible))
    words = segments[0].narration_text.split()[:65]
    writer.text(base + "presenter-test-script.txt", " ".join(words))
    writer.text(base + "scene-upload-checklist.md", "# Manual scene checklist\n\n- [ ] Founder independently approves avatar generation\n- [ ] Confirm Terry candidate\n- [ ] Run a 20–30 second manual test only after approval\n- [ ] Preserve evidence-led scenes\n- [ ] Do not publish")
    writer.text(base + "avatar-evaluation-scorecard.md", "# Avatar evaluation scorecard\n\nScore lip sync, expression, eye line, naturalness, continuity, trust, and brand fit.")
    writer.text(base + "visual-continuity-guide.md", "# Visual continuity\n\nUse consistent framing and restrained motion. Alternate presenter moments with real AuraAI evidence, screenshots, motion graphics, and founder-supplied media.")
