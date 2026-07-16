"""Editor-neutral timeline, subtitle, and founder-capture exports."""
from __future__ import annotations
import textwrap
from production_connector.exporter import PackageWriter
from production_connector.models import ScriptSegment

CAPTURES = [
 ("early-code","early-transcript-processing-code.mp4","Early transcript-processing code","Scroll through the narrow workflow"),
 ("git-history","git-history.mp4","Git history","Show relevant checkpoints"), ("dashboard","auraai-dashboard.mp4","AuraAI dashboard","Navigate mission state"),
 ("mission-terminal","mission-execution-terminal.mp4","Mission execution terminal","Run or replay safe mission output"), ("roster","employee-company-roster.png","Employee/company roster","Show software roles"),
 ("quality-breakdown","creative-quality-breakdown.mp4","Creative Quality breakdown","Open revised 89.28 score"), ("subtitle-failure","subtitle-43-character-failure.png","Subtitle failure","Show 43-character validation failure"),
 ("subtitle-correction","subtitle-correction.mp4","Subtitle correction","Show wrapped correction"), ("test-result","test-result.png","Test result","Show current verified suite result"),
 ("founder-review","founder-review-gate.mp4","Founder review gate","Show render/publish separation"), ("youtube-profile","youtube-profile.png","YouTube profile","Open @AuraAIMedia"),
 ("social-profile","selected-social-profile.png","Selected social profile","Open founder-selected public profile")]

def _timestamp(seconds: float, vtt: bool=False) -> str:
    millis=round(seconds*1000); h,millis=divmod(millis,3600000); m,millis=divmod(millis,60000); s,ms=divmod(millis,1000)
    return f"{h:02d}:{m:02d}:{s:02d}{'.' if vtt else ','}{ms:03d}"

def subtitle_cues(segments: list[ScriptSegment]) -> list[tuple[float,float,str]]:
    cues=[]; cursor=0.0
    for segment in segments:
        chunks=[]
        for sentence in segment.narration_text.split(". "):
            chunks.extend(textwrap.wrap(sentence.rstrip(".")+".", width=41, break_long_words=False, break_on_hyphens=False))
        for i in range(0,len(chunks),2):
            text="\n".join(chunks[i:i+2]); chars=len(text.replace("\n","")); duration=max(chars/20,1.2)
            cues.append((cursor,cursor+duration,text)); cursor+=duration
    return cues

def export(writer: PackageWriter, segments: list[ScriptSegment]) -> None:
    base="editor-package/"; cues=subtitle_cues(segments)
    writer.text(base+"edit-plan.md", "# Edit plan\n\n1920x1080, 30 fps, YouTube-safe margins. Evidence first; avoid continuous avatar, fake evidence, automatic stock downloads, copyrighted music, and robot-montage styling.")
    rows=[]; cursor=0.0
    for s in segments:
        rows.append({"order":s.order,"segment_id":s.segment_id,"start_seconds":round(cursor,3),"duration_seconds":s.estimated_duration_seconds,"visual_type":s.visual_type.value,"avatar_visible":s.avatar_visible}); cursor+=s.estimated_duration_seconds
    writer.json(base+"edit-decision-list.json", rows); writer.csv(base+"scene-order.csv", rows)
    srt=[]; vtt=["WEBVTT",""]
    for n,(start,end,text) in enumerate(cues,1):
        srt += [str(n),f"{_timestamp(start)} --> {_timestamp(end)}",text,""]
        vtt += [f"{_timestamp(start,True)} --> {_timestamp(end,True)}",text,""]
    writer.text(base+"subtitle-track.srt","\n".join(srt)); writer.text(base+"subtitle-track.vtt","\n".join(vtt))
    writer.json(base+"asset-map.json", {s.segment_id:s.asset_requirement_ids for s in segments})
    writer.text(base+"missing-assets.md", "# Missing assets\n\nAll founder captures are initially missing:\n\n"+"\n".join(f"- [ ] {x[0]}" for x in CAPTURES))
    writer.text(base+"audio-mix-guide.md", "# Audio mix\n\nPrioritize intelligible narration; use only licensed founder-approved music. No copyrighted music is included.")
    writer.text(base+"motion-style-guide.md", "# Motion style\n\nUse restrained, purpose-led motion with readable hold times; no default robot montage.")
    writer.text(base+"transition-guide.md", "# Transitions\n\nPrefer cuts, short dissolves, and evidence-motivated screen moves. Avoid distracting templates.")
    writer.text(base+"export-settings.md", "# Export settings\n\n- 1920x1080\n- 30 fps\n- YouTube-safe margins\n- Review-only private output after separate approval\n- Publishing disabled")

def export_founder_capture(writer: PackageWriter) -> None:
    base="founder-capture/"; entries=[]
    for asset_id,filename,screen,action in CAPTURES:
        entries.append({"asset_requirement_id":asset_id,"filename":filename,"screen_or_page_to_open":screen,"action_to_perform":action,"expected_duration_seconds":8,"scene_usage":[asset_id],"resolution":"1920x1080","cursor_movement_useful":filename.endswith(".mp4"),"sensitive_information_to_hide":["API keys","tokens","email addresses","private paths","personal notifications"],"audio_needed":False,"present":False})
    writer.json(base+"capture-manifest.json",entries)
    writer.text(base+"capture-checklist.md","# Founder capture checklist\n\n"+"\n".join(f"- [ ] `{e['filename']}` — {e['action_to_perform']}" for e in entries))
    writer.text(base+"privacy-checklist.md","# Privacy checklist\n\n- [ ] Hide API keys, tokens, emails, private paths, notifications, browser sessions, and unrelated files\n- [ ] Review every frame before sharing")
    writer.text(base+"recording-settings.md","# Recording settings\n\nRecord 1920x1080 at 30 fps. Disable notifications. Use deliberate cursor movement only where useful. System audio is not needed.")
    writer.text(base+"file-naming-guide.md","# File naming guide\n\nUse the exact lowercase filenames in `capture-manifest.json`; do not append secrets, usernames, or dates.")
