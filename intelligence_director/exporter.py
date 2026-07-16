"""Atomic, bounded Intelligence Director report exports."""
from __future__ import annotations
import csv,json,os
from pathlib import Path
from typing import Any
from intelligence_director.exceptions import IntelligenceDirectorError
from intelligence_director.models import IntelligenceResult
DISCLOSURE="Offline deterministic analysis. No live web research occurred. Scores are local heuristics. Founder approval required. No content mission executed. Nothing rendered or published."
class IntelligenceExporter:
    def __init__(self,root:Path): self.root=root.resolve()
    def export(self,result:IntelligenceResult)->Path:
        run_root=self._target(str(result.run.run_id))
        if run_root.exists(): raise IntelligenceDirectorError("Run export already exists.",code="RUN_EXISTS")
        files={"run/run-summary.json":result,"signals/normalized-signals.json":result.signals,"authority/source-authority.json":result.authority_assessments,"evidence/evidence-weights.json":result.evidence_weights,"evidence/evidence-conflicts.json":result.contradictions,"freshness/freshness-report.json":result.freshness,"queue/research-queue.json":result.queue,"handoff/web-research-plan-request.json":result.web_plan_request,"handoff/content-opportunity-context.json":result.content_context}
        for name,value in files.items(): self._write(run_root/name,json.dumps(self._dump(value),indent=2,sort_keys=True)+"\n")
        for name,title in {"run/run-summary.md":"Run summary","run/methodology.md":"Methodology","signals/normalized-signals.md":"Normalized signals","authority/source-authority.md":"Source authority","evidence/founder-verification-checklist.md":"Founder verification checklist","freshness/refresh-calendar.md":"Refresh calendar","queue/research-queue.md":"Research queue","handoff/founder-decision-template.md":"Founder decision template"}.items(): self._write(run_root/name,f"# {title}\n\n{DISCLOSURE}\n")
        rows=[["order","topic","priority","status"]]+[[str(x.order),self._csv(x.research_question.text),str(x.priority_score.overall),x.execution_status.value] for x in result.queue.items]
        self._write(run_root/"queue/queue-summary.csv","\n".join(",".join(self._csv(v) for v in row) for row in rows)+"\n")
        return run_root
    def _target(self,name:str)->Path:
        target=(self.root/name).resolve()
        try: target.relative_to(self.root)
        except ValueError as exc: raise IntelligenceDirectorError("Unsafe export path.",code="UNSAFE_PATH") from exc
        return target
    @staticmethod
    def _dump(value:Any)->Any:
        if value is None:return None
        if hasattr(value,"model_dump"): return value.model_dump(mode="json")
        return [IntelligenceExporter._dump(x) for x in value] if isinstance(value,list) else value
    @staticmethod
    def _csv(value:Any)->str:
        text=str(value).replace('"','""')
        if text.lstrip().startswith(("=","+","-","@")): text="'"+text
        return '"'+text+'"'
    @staticmethod
    def _write(path:Path,text:str)->None:
        path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_suffix(path.suffix+".tmp")
        with temporary.open("x",encoding="utf-8",newline="") as handle: handle.write(text); handle.flush(); os.fsync(handle.fileno())
        temporary.replace(path)
