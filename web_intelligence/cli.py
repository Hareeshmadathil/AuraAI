"""Safe CLI; performs no browsing unless an approved injected runtime exists."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from pydantic import ValidationError
from web_intelligence.approvals import ApprovalService
from web_intelligence.composition import create_offline_demo_service
from web_intelligence.exporter import WebReportExporter
from web_intelligence.models import CrawlLimits,WebResearchPlan
from web_intelligence.url_safety import UrlSafetyValidator

def parser()->argparse.ArgumentParser:
    value=argparse.ArgumentParser(description="Founder-controlled web intelligence (offline by default).")
    group=value.add_mutually_exclusive_group(required=True)
    for flag in ("check-environment","list-adapters","show-policy","validate-url","prepare-plan","approve-plan","crawl-public","browse-read-only","show-evidence","export-report","demo"):
        group.add_argument("--"+flag,action="store_true")
    value.add_argument("--url"); value.add_argument("--domain",action="append",default=[]); value.add_argument("--objective"); value.add_argument("--question")
    value.add_argument("--plan",type=Path); value.add_argument("--output",type=Path); value.add_argument("--founder-confirmed",action="store_true")
    value.add_argument("--max-pages",type=int,default=5)
    return value
def _load(path:Path)->WebResearchPlan: return WebResearchPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
def main(argv:list[str]|None=None)->int:
    args=parser().parse_args(argv); service=create_offline_demo_service()
    try:
        if args.check_environment:
            print("mode=offline python_compatible=true browser_limit=1 live_browsing=false"); return 0
        if args.list_adapters:
            for item in service.dashboard_state().adapters: print(f"adapter={item.kind.value} available={str(item.available).lower()} version={item.version or 'builtin'}")
            return 0
        if args.show_policy: print("READ ONLY; NO LOGIN; NO FORMS; NO DOWNLOADS; NO UPLOADS; NO PUBLISHING; robots.txt required"); return 0
        if args.validate_url:
            if not args.url or not args.domain: raise ValueError("--url and --domain are required.")
            print("valid_url="+UrlSafetyValidator(args.domain).validate(args.url)); return 0
        if args.prepare_plan:
            if not(args.objective and args.question and args.domain and args.output): raise ValueError("Objective, question, domain, and output are required.")
            plan=service.draft_plan(objective=args.objective,question=args.question,domains=args.domain,limits=CrawlLimits(maximum_pages=args.max_pages))
            print("plan_prepared="+str(WebReportExporter(args.output.parent).export_plan(plan,args.output.name))); return 0
        if args.approve_plan:
            if not(args.plan and args.output and args.founder_confirmed): raise ValueError("Plan, output, and --founder-confirmed are required.")
            approved,_=ApprovalService().approve(_load(args.plan),founder_confirmed=True)
            print("plan_approved="+str(WebReportExporter(args.output.parent).export_plan(approved,args.output.name))); return 0
        if args.crawl_public or args.browse_read_only:
            print("blocked=true reason=live execution requires an injected adapter, approved plan, hash match, unexpired approval, domain allowlist, and founder confirmation"); return 2
        if args.show_evidence: print(f"evidence_count={len(service.evidence)}"); return 0
        if args.export_report:
            if not args.output: raise ValueError("--output is required.")
            print("report="+str(WebReportExporter(args.output.parent).export_report(service.evidence,service.citations,args.output.name))); return 0
        print("demo=offline pending_plans=1 publishing=false"); return 0
    except (OSError,ValueError,ValidationError) as error:
        print(f"safe_failure={error.__class__.__name__}"); return 1
if __name__=="__main__": raise SystemExit(main())
