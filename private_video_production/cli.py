"""Safe command line interface for local private video production."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import AuraAIError

from private_video_production.composition import PrivateVideoComposition
from private_video_production.exporter import PrivateVideoProductionExporter
from private_video_production.pipeline import PrivateVideoProductionPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AuraAI private video production")
    parser.add_argument("--check-environment", action="store_true")
    parser.add_argument("--list-voices", action="store_true")
    parser.add_argument("--mission-package", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/private-video"))
    parser.add_argument("--voice")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--create-voice-audition", action="store_true")
    parser.add_argument("--generate-narration", action="store_true")
    parser.add_argument("--build-timeline", action="store_true")
    parser.add_argument("--render-preview", action="store_true")
    parser.add_argument("--render-private-draft", action="store_true")
    parser.add_argument("--content-approved", action="store_true")
    parser.add_argument("--private-render-approved", action="store_true")
    parser.add_argument("--founder-confirmed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.check_environment or args.list_voices:
            composition = PrivateVideoComposition.create(args.output_root.resolve())
            if args.check_environment:
                for capability in composition.capabilities:
                    print(f"{capability.capability_name}: {'available' if capability.available else 'unavailable'}")
            if args.list_voices:
                voices = composition.voice_service.list_voices()
                for voice in voices:
                    print(f"{voice.name} | {voice.culture} | {voice.gender or 'unspecified'}")
                if not voices:
                    print("No local voices available.")
            return 0
        if args.mission_package is None:
            raise ValueError("--mission-package is required for production commands.")
        target = (args.output_root / args.mission_package.resolve().name).resolve()
        composition = PrivateVideoComposition.create(target)
        pipeline = PrivateVideoProductionPipeline(
            voice_service=composition.voice_service,
            capabilities=composition.capabilities,
            ffmpeg_runner=composition.ffmpeg_runner,
        )
        result, export_path = pipeline.prepare(args.mission_package, target, export=True)
        if args.prepare or args.build_timeline:
            if args.build_timeline:
                result = pipeline.record_approval(
                    result,
                    content_approved=args.content_approved,
                    private_render_approved=False,
                    founder_confirmed=args.founder_confirmed,
                )
                PrivateVideoProductionExporter(target).export(result)
            print(f"mission_id: {result.production_input.mission_id}")
            print(f"status: {result.status.value}")
            print(f"output_path: {export_path}")
            print("published: false")
            return 0
        if args.create_voice_audition:
            if not args.voice:
                raise ValueError("--voice must name an installed local voice.")
            voice_result = pipeline.audition(result, args.voice)
            print(f"voice selected: {voice_result.voice_name}")
            print(f"duration: {voice_result.duration_seconds:.2f}")
            print(f"sample rate: {voice_result.sample_rate}")
            print(f"output path: {target / voice_result.output_relative_path}")
            return 0
        if args.generate_narration:
            if not args.voice:
                raise ValueError("--voice must name an installed local voice.")
            result = pipeline.record_approval(
                result,
                content_approved=args.content_approved,
                private_render_approved=False,
                founder_confirmed=args.founder_confirmed,
            )
            result = pipeline.generate_narration(result, args.voice)
            PrivateVideoProductionExporter(target).export(result)
            print(f"voice selected: {result.selected_voice.name}")
            print(f"narration duration: {result.voice_result.duration_seconds:.2f}")
            print(f"output path: {target / result.voice_result.output_relative_path}")
            print("published: false")
            return 0
        if args.render_preview or args.render_private_draft:
            result = pipeline.record_approval(
                result,
                content_approved=args.content_approved,
                private_render_approved=args.private_render_approved,
                founder_confirmed=args.founder_confirmed,
            )
            result = pipeline.recover_narration(result)
            result = pipeline.render(result, preview=args.render_preview)
            PrivateVideoProductionExporter(target).export(result)
            print(f"render status: {result.render_result.status.value}")
            print(f"verified: {result.render_result.verified}")
            print(f"output path: {target / result.render_result.output_relative_path}")
            print("published: false")
            return 0 if result.render_result.verified else 1
        raise ValueError("Select one private video production command.")
    except (AuraAIError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
