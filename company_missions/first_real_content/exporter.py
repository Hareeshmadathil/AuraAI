"""Explicit, atomic, path-safe export boundary for review artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core import ValidationError
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
            "quality/quality-summary.md": f"# Quality summary\n\nScore: {result.production_review.quality_score}\nGate: {result.founder_review.gate_status}\n",
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
        return payloads

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif isinstance(value, list):
            value = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
        return json.dumps(value, indent=2, sort_keys=True) + "\n"

    @staticmethod
    def _review_markdown(result: FirstContentMissionResult) -> str:
        return (
            f"# Founder review: {result.mission.title}\n\n"
            f"State: {result.mission.status.value}\n\n"
            f"Quality: {result.production_review.quality_score}\n\n"
            "**FOUNDER REVIEW REQUIRED**\n\n**NOT RENDERED**\n\n**NOT PUBLISHED**\n"
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
