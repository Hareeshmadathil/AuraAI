"""Offline YouTube metadata preparation exporter."""
from production_connector.exporter import PackageWriter
from production_connector.models import MissionPackage, ScriptSegment

def export(writer: PackageWriter, package: MissionPackage, segments: list[ScriptSegment]) -> None:
    base="youtube-package/"
    writer.text(base+"title-options.txt", package.title + "\nHow AuraAI Built a Founder-Controlled AI Media Workflow\nMission Zero: What Building an AI Company Actually Takes")
    writer.text(base+"description.md", "# Description\n\nA founder-reviewed look at AuraAI’s architecture, real failures, production safeguards, and Mission Zero revision. Claims shown on screen require founder-supplied evidence.\n\nNo automated upload or publication occurred.")
    cursor=0.0; chapters=[]
    for s in segments:
        chapters.append(f"{int(cursor)//60:02d}:{int(cursor)%60:02d} {s.section_title}"); cursor += s.estimated_duration_seconds
    writer.text(base+"chapters.txt", "\n".join(chapters)); writer.text(base+"tags.txt", "AuraAI, AI agents, Python, Mission Zero, creator operating system, AI media company")
    writer.text(base+"hashtags.txt", "#AuraAI #AIAgents #Python"); writer.text(base+"pinned-comment.md", "Which founder-controlled boundary should AuraAI test next? Publishing remains unapproved.")
    writer.text(base+"thumbnail-brief.md", "# Thumbnail brief\n\nTruthful contrast: code-to-company transformation. Use real AuraAI UI or founder portrait; no fake evidence, misleading metrics, or robot montage.")
    writer.text(base+"upload-checklist.md", "# Upload checklist\n\n- [ ] Verify every factual claim\n- [ ] Confirm rights for all media\n- [ ] Review subtitles and safe margins\n- [ ] Obtain separate founder publishing approval\n- [ ] Upload manually only after approval")
    writer.json(base+"publishing-status.json", {"uploaded": False, "published": False, "founder_publish_approval": False})
