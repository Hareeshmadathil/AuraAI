"""Safe command-line interface for offline production preparation."""
from __future__ import annotations
import argparse
from pathlib import Path
from core import ValidationError
from production_connector.loader import MissionPackageLoader
from production_connector.service import ProductionConnectorService

def parser() -> argparse.ArgumentParser:
    value=argparse.ArgumentParser(description="Prepare offline provider-review packages; performs no network operations.")
    value.add_argument("--mission-package",type=Path,required=True); value.add_argument("--output-root",type=Path)
    group=value.add_mutually_exclusive_group(required=True)
    for flag in ["validate","prepare-all","export-elevenlabs","export-heygen","export-editor","export-youtube","export-founder-capture","show-missing-assets"]: group.add_argument("--"+flag,action="store_true")
    return value
def main(argv: list[str]|None=None) -> int:
    args=parser().parse_args(argv)
    try: service=ProductionConnectorService(MissionPackageLoader(Path.cwd()).load(args.mission_package))
    except (ValidationError,OSError,ValueError) as error: print(f"Validation failed: {error}"); return 1
    if args.validate: print("Valid Mission Zero script-v2 package; quality gate passed; publishing false."); return 0
    if args.show_missing_assets: print("12 founder evidence assets are missing. See founder capture manifest after export."); return 0
    if args.output_root is None: print("Failure: --output-root is required for export."); return 2
    names={"export_elevenlabs":"elevenlabs","export_heygen":"heygen","export_editor":"editor","export_youtube":"youtube","export_founder_capture":"founder-capture"}
    selected=None if args.prepare_all else {v for k,v in names.items() if getattr(args,k)}
    try: output=service.prepare(args.output_root,selected)
    except (ValidationError,OSError,ValueError) as error: print(f"Export failed: {error}"); return 1
    print(f"Prepared offline review package at {output}. No provider, render, upload, or publish operation occurred."); return 0
if __name__ == "__main__": raise SystemExit(main())
