"""Explicit, atomic, path-safe export boundary for review artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core import ValidationError
from creative_quality.intelligence import (
    CreativeQualityIntelligence,
    render_quality_breakdown_markdown,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventType

from company_missions.first_real_content.manifest import (
    ArtifactManifest,
    ArtifactManifestEntry,
)
from company_missions.first_real_content.models import FirstContentMissionResult


class FirstContentMissionExporter:
    """Export a complete review package without rendering or publishing."""

    _FORBIDDEN_MARKERS = frozenset(
        {
            "api_key",
            "api key",
            "authorization",
            "raw_prompt",
            "raw prompt",
            "raw_response",
            "raw response",
            "x-goog-api-key",
        }
    )

    def __init__(
        self,
        output_root: Path,
        *,
        overwrite: bool = False,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self._root = output_root.resolve()
        self._overwrite = overwrite
        self._events = event_bus

    def export(self, result: FirstContentMissionResult) -> tuple[Path, ArtifactManifest]:
        target = (self._root / str(result.mission.mission_id)).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as error:
            raise ValidationError("Unsafe export path.", error_code="UNSAFE_EXPORT_PATH") from error
        if target.exists() and not self._overwrite:
            raise ValidationError(
                "Mission export already exists.", error_code="MISSION_EXPORT_EXISTS"
            )
        payloads = self._payloads(result)
        self._validate_safe(payloads)
        entries: list[ArtifactManifestEntry] = []
        try:
            for relative_path, content in payloads.items():
                raw = content.encode("utf-8")
                path = target / relative_path
                self._atomic_write(path, raw)
                entries.append(
                    ArtifactManifestEntry(
                        relative_path=relative_path,
                        media_type=("application/json" if relative_path.endswith(".json") else "text/plain"),
                        size_bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest(),
                    )
                )
            manifest = ArtifactManifest(
                mission_id=result.mission.mission_id, artifacts=entries
            )
            manifest_bytes = self._json(manifest).encode("utf-8")
            self._atomic_write(target / "manifest/artifact-manifest.json", manifest_bytes)
            checksums = {item.relative_path: item.sha256 for item in entries}
            checksums["manifest/artifact-manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()
            self._atomic_write(
                target / "manifest/sha256.json",
                (json.dumps(checksums, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        except OSError as error:
            raise ValidationError("Mission export failed safely.", error_code="MISSION_EXPORT_FAILED") from error
        if self._events is not None:
            self._events.emit(
                RuntimeEventType.ARTIFACTS_EXPORTED,
                "Mission review artifacts exported.",
                mission_id=result.mission.mission_id,
            )
        return target, manifest

    def _payloads(self, result: FirstContentMissionResult) -> dict[str, str]:
        pilot = result.pilot
        scripts = result.script_versions
        breakdown = result.creative_quality_package.quality_breakdown
        if breakdown is None:
            breakdown = CreativeQualityIntelligence().build(
                result.creative_quality_package
            )
        payloads = {
            "mission/mission.json": self._json(result.mission),
            "mission/history.json": self._json(result.mission.history),
            "research/research.json": self._json(pilot.research_artifact),
            "research/research-summary.md": f"# Research summary\n\n{pilot.research_artifact.executive_summary}\n",
            "seo/seo.json": self._json(pilot.seo_artifact),
            "seo/title-options.txt": "\n".join(pilot.seo_artifact.title_options) + "\n",
            "seo/tags.txt": "\n".join([pilot.seo_artifact.primary_keyword, *pilot.seo_artifact.secondary_keywords]) + "\n",
            "seo/hashtags.txt": "\n".join(pilot.seo_artifact.hashtags) + "\n",
            "quality/creative-quality.json": self._json(result.creative_quality_package),
            "quality/quality-summary.md": (
                f"# Quality summary\n\n"
                f"Score: {result.production_review.quality_score}\n"
                f"Gate: {result.founder_review.gate_status}\n\n"
                "[Open the full Creative Quality breakdown]"
                "(quality-breakdown.md)\n"
            ),
            "quality/quality-breakdown.json": self._json(breakdown),
            "quality/quality-breakdown.md": (
                render_quality_breakdown_markdown(breakdown)
            ),
            "production/production-package.json": self._json(result.production_package),
            "production/thumbnail-concepts.json": self._json(result.production_package.thumbnail_plan),
            "production/shorts-package.json": self._json(result.production_package.short_form_package),
            "production/metadata-package.json": self._json(result.metadata_review),
            "founder-review/review-package.json": self._json(result.founder_review),
            "founder-review/review-summary.md": self._review_markdown(result),
        }
        for index, script in enumerate(scripts, start=1):
            payloads[f"script/script-v{index}.json"] = self._json(script)
            payloads[f"script/script-v{index}.md"] = (
                f"# {script.title}\n\n{script.hook}\n\n"
                + "\n\n".join(script.sections)
                + f"\n\n## Call to action\n\n{script.call_to_action}\n"
            )
        if result.revision_request is not None:
            payloads.update(self._revision_payloads(result))
        return payloads

    def _revision_payloads(
        self,
        result: FirstContentMissionResult,
    ) -> dict[str, str]:
        if (
            result.quality_comparison is None
            or len(result.production_versions) != 2
            or len(result.quality_versions) != 2
        ):
            raise ValidationError(
                "Controlled revision export requires both artifact versions.",
                error_code="REVISION_EXPORT_INCOMPLETE",
            )
        original_quality, revised_quality = result.quality_versions
        original_breakdown = original_quality.quality_breakdown
        revised_breakdown = revised_quality.quality_breakdown
        intelligence = CreativeQualityIntelligence()
        if original_breakdown is None:
            original_breakdown = intelligence.build(original_quality)
        if revised_breakdown is None:
            revised_breakdown = intelligence.build(revised_quality)
        original_production, revised_production = result.production_versions
        return {
            "quality/original/creative-quality.json": self._json(
                original_quality
            ),
            "quality/original/quality-breakdown.json": self._json(
                original_breakdown
            ),
            "quality/original/quality-breakdown.md": (
                render_quality_breakdown_markdown(original_breakdown)
            ),
            "quality/revised/creative-quality.json": self._json(revised_quality),
            "quality/revised/quality-breakdown.json": self._json(
                revised_breakdown
            ),
            "quality/revised/quality-breakdown.md": (
                render_quality_breakdown_markdown(revised_breakdown)
            ),
            "production/original/production-package.json": self._json(
                original_production
            ),
            "production/revised/production-package.json": self._json(
                revised_production
            ),
            "revision/revision-request.json": self._json(
                result.revision_request
            ),
            "revision/revision-request.md": (
                f"# Founder revision request\n\n{result.revision_request.notes}\n\n"
                + "\n".join(
                    f"- {item}" for item in result.revision_request.objectives
                )
                + "\n"
            ),
            "revision/score-comparison.json": self._json(
                result.quality_comparison
            ),
            "revision/score-comparison.md": self._comparison_markdown(result),
            "mission/artifact-version-history.json": self._json(
                result.mission.produced_artifacts
            ),
            "mission/artifact-version-history.md": self._history_markdown(
                result
            ),
        }

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif isinstance(value, list):
            value = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
        return json.dumps(value, indent=2, sort_keys=True) + "\n"

    @staticmethod
    def _review_markdown(result: FirstContentMissionResult) -> str:
        comparison = (
            "\n[Compare original and revised quality scores]"
            "(../revision/score-comparison.md)\n"
            if result.quality_comparison is not None
            else ""
        )
        return (
            f"# Founder review: {result.mission.title}\n\n"
            f"State: {result.mission.status.value}\n\n"
            f"Quality: {result.production_review.quality_score}\n\n"
            "[Open the full Creative Quality breakdown]"
            "(../quality/quality-breakdown.md)\n\n"
            f"{comparison}"
            "**FOUNDER REVIEW REQUIRED**\n\n**NOT RENDERED**\n\n**NOT PUBLISHED**\n"
        )

    @staticmethod
    def _comparison_markdown(result: FirstContentMissionResult) -> str:
        comparison = result.quality_comparison
        if comparison is None:
            raise ValidationError("Quality comparison is unavailable.")
        rows = "\n".join(
            f"| {item.department.value.title()} | {item.original_score:.2f} | "
            f"{item.revised_score:.2f} | {item.change:+.2f} |"
            for item in comparison.departments
        )
        return (
            "# Mission Zero quality comparison\n\n"
            f"Original overall: **{comparison.original_overall_score:.2f}**\n\n"
            f"Revised overall: **{comparison.revised_overall_score:.2f}**\n\n"
            f"Change: **{comparison.overall_change:+.2f}**\n\n"
            "| Department | Original | Revised | Change |\n"
            "| --- | ---: | ---: | ---: |\n"
            f"{rows}\n\n"
            f"Original blockers: {comparison.original_blocker_count}\n\n"
            f"Revised blockers: {comparison.revised_blocker_count}\n\n"
            "**FOUNDER REVIEW REQUIRED**\n\n"
            "**NOT RENDERED**\n\n"
            "**NOT PUBLISHED**\n"
        )

    @staticmethod
    def _history_markdown(result: FirstContentMissionResult) -> str:
        rows = "\n".join(
            f"| {item.artifact_type.value} | {item.name} | "
            f"{item.version_number} | {item.status.value} | "
            f"{item.parent_artifact_id or '—'} |"
            for item in result.mission.produced_artifacts
        )
        return (
            "# Mission Zero artifact version history\n\n"
            "| Type | Name | Version | Status | Parent |\n"
            "| --- | --- | ---: | --- | --- |\n"
            f"{rows}\n"
        )

    def _validate_safe(self, payloads: dict[str, str]) -> None:
        lowered = "\n".join(payloads.values()).lower()
        if any(marker in lowered for marker in self._FORBIDDEN_MARKERS):
            raise ValidationError("Unsafe export field detected.", error_code="UNSAFE_EXPORT_CONTENT")

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
