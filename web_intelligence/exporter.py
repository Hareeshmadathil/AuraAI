"""Safe deterministic plan/evidence report export."""
import json
from pathlib import Path
from web_intelligence.exceptions import WebIntelligenceError
from web_intelligence.models import Citation,EvidenceItem,WebResearchPlan
class WebReportExporter:
    def __init__(self,root:Path): self.root=root.resolve()
    def _target(self,name:str)->Path:
        target=(self.root/name).resolve()
        try: target.relative_to(self.root)
        except ValueError as error: raise WebIntelligenceError("Unsafe export path.",error_code="UNSAFE_EXPORT_PATH") from error
        return target
    def export_plan(self,plan:WebResearchPlan,name:str="web-research-plan.json")->Path:
        target=self._target(name); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(plan.model_dump(mode="json"),indent=2,sort_keys=True)+"\n",encoding="utf-8"); return target
    def export_report(self,evidence:list[EvidenceItem],citations:list[Citation],name:str="web-research-report.json")->Path:
        target=self._target(name); target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({"evidence":[x.model_dump(mode="json") for x in evidence],"citations":[x.model_dump(mode="json") for x in citations]},indent=2,sort_keys=True,default=str)+"\n",encoding="utf-8"); return target
