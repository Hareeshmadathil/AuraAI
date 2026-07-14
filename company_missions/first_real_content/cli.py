"""Safe command line boundary for the first real content mission."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from providers.composition import create_provider_router
from providers.gemini.config import GeminiConfig
from providers.gemini.transport import HttpGeminiTransport

from company_missions.first_real_content.exporter import FirstContentMissionExporter
from company_missions.first_real_content.loader import FounderInputLoader
from company_missions.first_real_content.models import FirstContentMissionResult
from company_missions.first_real_content.runner import FirstRealContentMissionRunner


DEFAULT_REQUEST_BUDGET = 6


def _positive_request_budget(value: str) -> int:
    budget = int(value)
    if budget < 1 or budget > DEFAULT_REQUEST_BUDGET:
        raise argparse.ArgumentTypeError("request budget must be between 1 and 6")
    return budget


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a founder-reviewed content mission.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/missions"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--enable-live-gemini", action="store_true")
    parser.add_argument("--founder-approved-live-ai", action="store_true")
    parser.add_argument(
        "--request-budget",
        type=_positive_request_budget,
        default=DEFAULT_REQUEST_BUDGET,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        founder_input = FounderInputLoader(Path.cwd()).load(args.input)
        if args.dry_run:
            print("validated=true")
            print("mode=deterministic")
            print("founder_review_required=true")
            print("rendered=false")
            print("published=false")
            return 0
        live_requested = args.enable_live_gemini or args.founder_approved_live_ai
        if live_requested and not (
            args.enable_live_gemini and args.founder_approved_live_ai
        ):
            print("error_code=LIVE_AI_FLAGS_REQUIRED")
            return 2
        router = None
        if live_requested:
            if not founder_input.allow_live_gemini:
                print("error_code=LIVE_AI_NOT_ALLOWED_BY_INPUT")
                return 2
            if input("Type APPROVE to authorize bounded live AI: ").strip() != "APPROVE":
                print("error_code=LIVE_AI_CONFIRMATION_REQUIRED")
                return 2
            key = getpass.getpass("Gemini API key: ")
            config = GeminiConfig(
                enabled=True,
                api_key=key,
                allow_live_requests=True,
                request_budget=args.request_budget,
                maximum_retries=0,
                fallback_enabled=founder_input.allow_deterministic_fallback,
            )
            transport = HttpGeminiTransport(
                base_url=config.base_url, api_key=config.api_key_value
            )
            router = create_provider_router(config, transport)
            print(f"model={config.model}")
            print(f"request_budget={args.request_budget}")
        runner = FirstRealContentMissionRunner(
            provider_router=router,
            founder_approved_live_ai=live_requested,
        )
        operation = runner.run(founder_input)
        if not operation.success:
            print(f"error_code={operation.error_code or 'FIRST_CONTENT_MISSION_FAILED'}")
            return 1
        result = FirstContentMissionResult.model_validate(
            operation.data["first_content_mission_result"]
        )
        target, manifest = FirstContentMissionExporter(
            args.output_root, event_bus=runner.event_bus
        ).export(result)
        print(f"mission_id={result.mission.mission_id}")
        print(f"current_stage={result.mission.status.value}")
        print(f"fallback_used={str(result.provider_usage.fallback_used).lower()}")
        print(f"quality_score={result.production_review.quality_score}")
        print(f"export_directory={target}")
        print(f"artifact_count={len(manifest.artifacts)}")
        print("founder_review_required=true")
        print("rendered=false")
        print("published=false")
        return 0
    except Exception as error:
        print(f"error_code={getattr(error, 'error_code', 'FIRST_CONTENT_MISSION_FAILED')}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
