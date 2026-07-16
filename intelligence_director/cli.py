"""Network-free Intelligence Director CLI."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from pydantic import ValidationError
from intelligence_director.composition import create_demo_result
from intelligence_director.enums import SignalSource
from intelligence_director.exporter import IntelligenceExporter
from intelligence_director.models import IntelligenceSignal
def parser():
    p=argparse.ArgumentParser(); g=p.add_mutually_exclusive_group(required=True)
    for option in ("list-signal-types","validate-signal","run-analysis","show-priorities","show-contradictions","show-freshness","show-research-queue","prepare-web-plan","prepare-content-context","export-report","demo"): g.add_argument("--"+option,action="store_true")
    p.add_argument("--input",type=Path); p.add_argument("--output-root",type=Path,default=Path("outputs/intelligence-director")); return p
def main(argv=None)->int:
    args=parser().parse_args(argv)
    try:
        if args.list_signal_types: print("\n".join(x.value for x in SignalSource)); return 0
        if args.validate_signal:
            if args.input is None or args.input.stat().st_size>1_000_000: raise ValueError("A bounded input file is required.")
            IntelligenceSignal.model_validate_json(args.input.read_text(encoding="utf-8")); print("valid=true"); return 0
        r=create_demo_result()
        if args.export_report: print(f"exported={IntelligenceExporter(args.output_root).export(r)}"); return 0
        if args.show_priorities: print("\n".join(f"{x.band.value} score={x.overall:.2f}" for x in r.priorities)); return 0
        if args.show_contradictions: print(f"contradictions={len(r.contradictions)}"); return 0
        if args.show_freshness: print("\n".join(x.status.value for x in r.freshness)); return 0
        if args.show_research_queue: print(f"queue_items={len(r.queue.items)} approval={r.queue.founder_approval_status.value} execution=false"); return 0
        if args.prepare_web_plan: print(f"plan_hash={r.web_plan_request.plan_hash} founder_approval=true live_execution=false"); return 0
        if args.prepare_content_context: print(f"context_id={r.content_context.context_id} mission_executed=false published=false"); return 0
        print(f"synthetic=true signals={len(r.signals)} queue={len(r.queue.items)} offline=true founder_approval_required=true live_research=false mission_executed=false rendered=false published=false"); return 0
    except (ValueError,OSError,ValidationError,Exception) as exc:
        print(f"error={exc.__class__.__name__}"); return 2
if __name__=="__main__": raise SystemExit(main())
