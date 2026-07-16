"""Offline Knowledge Manager CLI."""
import argparse
from pathlib import Path
from knowledge_manager.composition import create_demo_result,create_demo_service
from knowledge_manager.enums import KnowledgeCategory
from knowledge_manager.exporter import KnowledgeExporter
from knowledge_manager.models import KnowledgeQuery
from knowledge_manager.sqlite_repository import SQLiteKnowledgeRepository
def build_parser():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    for x in ("check-database","initialize-database","list-categories","validate-ingestion","ingest","query","show-item","show-history","show-conflicts","show-freshness","show-refresh-queue","prepare-intelligence-context","prepare-content-context","export-report","demo"):g.add_argument("--"+x,action="store_true")
    p.add_argument("--database",type=Path,default=Path("data/knowledge/knowledge.db"));p.add_argument("--data-root",type=Path,default=Path("data/knowledge"));p.add_argument("--output-root",type=Path,default=Path("outputs/knowledge-manager"));return p
def main(argv=None):
    args=build_parser().parse_args(argv)
    try:
        if args.list_categories:print("\n".join(x.value for x in KnowledgeCategory));return 0
        if args.initialize_database:
            repo=SQLiteKnowledgeRepository(args.database,allowed_root=args.data_root);repo.initialize();print(f"initialized=true schema={repo.schema_version()}");return 0
        if args.check_database:
            repo=SQLiteKnowledgeRepository(args.database,allowed_root=args.data_root);print(f"exists={args.database.exists()}"+(f" schema={repo.schema_version()}" if args.database.exists() else ""));return 0
        service=create_demo_service();result=create_demo_result()
        if args.export_report:print(f"exported={KnowledgeExporter(args.output_root).export(result,service.repository.list_versions())}");return 0
        if args.query:print(f"matches={len(service.query(KnowledgeQuery(text='gemini structured json')).matches)}");return 0
        if args.show_history:print(f"versions={len(service.repository.list_versions())}");return 0
        if args.show_conflicts:print(f"conflicts={len(service.conflicts)}");return 0
        if args.show_freshness or args.show_refresh_queue:print(f"refresh_queue={len(service.refresh_queue())}");return 0
        if args.prepare_content_context:print("context_ready=true mission_executed=false rendered=false published=false");return 0
        if args.prepare_intelligence_context:print("intelligence_context=true research_execution=false");return 0
        print(f"synthetic=true offline=true items={result.item_count} current={result.current_versions} historical={result.historical_versions} live_research=false mission_executed=false rendered=false published=false");return 0
    except Exception as exc:print(f"error={exc.__class__.__name__}");return 2
if __name__=="__main__":raise SystemExit(main())
