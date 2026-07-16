"""Atomic safe knowledge reports."""
import json,os
from pathlib import Path
from knowledge_manager.exceptions import KnowledgeManagerError
NOTICE="Local offline knowledge. No live research occurred. Freshness must be checked. Founder approval required where applicable. No mission executed. Nothing rendered or published."
class KnowledgeExporter:
    def __init__(self,root:Path):self.root=root.resolve()
    def export(self,result,versions)->Path:
        run_root=self._safe(str(result.run.run_id))
        if run_root.exists():raise KnowledgeManagerError("Run export already exists.",code="RUN_EXISTS")
        current=[v for v in versions if v.superseded_by is None]; history=[v for v in versions if v.superseded_by]
        data={"run/run-summary.json":result,"knowledge/current-knowledge.json":current,"knowledge/historical-versions.json":history,"conflicts/conflicts.json":result.conflicts,"freshness/freshness-report.json":[v.freshness for v in versions],"freshness/refresh-queue.json":result.refresh_queue,"retention/retention-decisions.json":[],"retrieval/sample-query-results.json":result.retrieval,"handoff/intelligence-director-context.json":{"missing_stale_or_conflicted":[x.knowledge_id for x in result.refresh_queue],"execution":False},"handoff/content-knowledge-context.json":result.context}
        for name,value in data.items():self._write(run_root/name,json.dumps(self._dump(value),indent=2,sort_keys=True)+"\n")
        for name,title in {"run/run-summary.md":"Run summary","run/methodology.md":"Methodology","knowledge/current-knowledge.md":"Current knowledge","conflicts/conflicts.md":"Conflicts","conflicts/founder-conflict-review.md":"Founder conflict review","freshness/refresh-calendar.md":"Refresh calendar","retention/retention-summary.md":"Retention summary","retrieval/sample-query-results.md":"Sample retrieval","handoff/founder-decision-template.md":"Founder decision"}.items():self._write(run_root/name,f"# {title}\n\n{NOTICE}\n")
        rows=[["topic","category","version","status"]]+[[v.topic.name,v.category.value,str(v.version),v.freshness.status.value] for v in versions]
        self._write(run_root/"knowledge/knowledge-index.csv","\n".join(",".join(self._csv(x) for x in row) for row in rows)+"\n");return run_root
    def _safe(self,name):
        target=(self.root/name).resolve()
        try:target.relative_to(self.root)
        except ValueError as exc:raise KnowledgeManagerError("Unsafe export path.",code="UNSAFE_PATH") from exc
        return target
    @staticmethod
    def _dump(x):
        if x is None:return None
        if hasattr(x,"model_dump"):return x.model_dump(mode="json")
        if isinstance(x,list):return [KnowledgeExporter._dump(v) for v in x]
        if isinstance(x,dict):return {k:KnowledgeExporter._dump(v) for k,v in x.items()}
        return str(x) if not isinstance(x,(str,int,float,bool)) else x
    @staticmethod
    def _csv(x):
        text=str(x).replace('"','""')
        if text.lstrip().startswith(("=","+","-","@")):text="'"+text
        return '"'+text+'"'
    @staticmethod
    def _write(path,text):
        path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp")
        with tmp.open("x",encoding="utf-8",newline="") as f:f.write(text);f.flush();os.fsync(f.fileno())
        tmp.replace(path)
