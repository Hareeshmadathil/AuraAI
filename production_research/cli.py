"""Offline CLI for the AI Production Research catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core import AuraAIError

from production_research.reporting import ProductionResearchReporter
from production_research.service import ProductionResearchService


def build_parser() -> argparse.ArgumentParser:
    """Create the production-research command parser."""

    parser = argparse.ArgumentParser(description="AuraAI AI Production Research")
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--list-providers", action="store_true")
    parser.add_argument("--show-provider", metavar="NAME")
    parser.add_argument(
        "--export-report",
        nargs="?",
        const=Path("outputs/production-research"),
        type=Path,
        metavar="DIRECTORY",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    service: ProductionResearchService | None = None,
) -> int:
    """Execute requested offline catalog operations."""

    parser = build_parser()
    args = parser.parse_args(argv)
    research = service or ProductionResearchService()
    if not any(
        (
            args.list_categories,
            args.list_providers,
            args.show_provider,
            args.export_report,
        )
    ):
        parser.print_help()
        return 0
    try:
        if args.list_categories:
            for category in research.list_categories():
                print(category.value)
        if args.list_providers:
            for provider in research.list_providers():
                print(
                    f"{provider.name} | {provider.category.value} | "
                    f"{provider.local_score} | {provider.status.value}"
                )
        if args.show_provider:
            print(
                json.dumps(
                    research.show_provider(args.show_provider).model_dump(mode="json"),
                    indent=2,
                )
            )
        if args.export_report:
            paths = ProductionResearchReporter().export(
                research.build_report(),
                args.export_report,
            )
            for path in paths:
                print(path)
        return 0
    except (AuraAIError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
