"""Checksums and validation for local review render artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from production.rendering.ffmpeg_runner import FFmpegRunner
from production.rendering.models import (
    RenderArtifactType,
    RenderExportManifest,
    RenderStatus,
    RenderValidationCheck,
    RenderValidationReport,
    RenderedArtifact,
)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 checksum for one local file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def completed_artifact(
    *,
    artifact_type: RenderArtifactType,
    path: Path,
    mime_type: str,
    sample_data: bool,
    source_references: Iterable[str] = (),
    warnings: Iterable[str] = (),
    duration_seconds: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> RenderedArtifact:
    """Build validated metadata for one completed local artifact."""

    resolved = path.resolve()
    return RenderedArtifact(
        artifact_type=artifact_type,
        path=resolved,
        mime_type=mime_type,
        size_bytes=resolved.stat().st_size,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        checksum_sha256=sha256_file(resolved),
        render_status=RenderStatus.REVIEW_REQUIRED,
        sample_data=sample_data,
        published=False,
        review_required=True,
        source_references=list(source_references),
        warnings=list(warnings),
    )


class RenderValidator:
    """Validate local artifacts, probes, checksums, and safety invariants."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner

    def validate(self, manifest: RenderExportManifest) -> RenderValidationReport:
        """Return transparent blockers rather than publishing any output."""

        checks: list[RenderValidationCheck] = []
        for artifact in manifest.artifacts:
            checks.extend(self._artifact_checks(artifact, manifest))
        checks.append(
            self._check(
                "Publish prohibition",
                not manifest.publish_allowed
                and all(not artifact.published for artifact in manifest.artifacts),
                "All local artifacts remain not published.",
                "A local artifact or manifest allows publishing.",
            )
        )
        checks.append(
            self._check(
                "Review requirement",
                manifest.review_required
                and all(artifact.review_required for artifact in manifest.artifacts),
                "Review-required labels are preserved.",
                "A review-required label is missing.",
            )
        )
        checks.append(
            self._check(
                "Manifest completeness",
                bool(manifest.stage_results) and bool(manifest.artifacts),
                "Render manifest contains stages and artifacts.",
                "Render manifest is incomplete.",
            )
        )
        blockers = [check.message for check in checks if check.blocking and not check.passed]
        warnings = [check.message for check in checks if not check.blocking and not check.passed]
        return RenderValidationReport(
            passed=not blockers,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    def _artifact_checks(
        self,
        artifact: RenderedArtifact,
        manifest: RenderExportManifest,
    ) -> list[RenderValidationCheck]:
        root = manifest.settings.output_root
        try:
            artifact.path.resolve().relative_to(root)
            inside = True
        except ValueError:
            inside = False
        exists = artifact.path.is_file() and artifact.path.stat().st_size > 0
        checksum_matches = (
            exists
            and artifact.checksum_sha256 is not None
            and sha256_file(artifact.path) == artifact.checksum_sha256
        )
        checks = [
            self._check(
                f"Path safety: {artifact.artifact_id}",
                inside,
                "Artifact remains inside the configured root.",
                "Artifact path escapes the configured root.",
            ),
            self._check(
                f"File exists: {artifact.artifact_id}",
                exists,
                "Artifact exists and is nonempty.",
                "Declared artifact is missing or empty.",
            ),
            self._check(
                f"Checksum: {artifact.artifact_id}",
                checksum_matches,
                "Artifact checksum matches.",
                "Artifact checksum does not match.",
            ),
        ]
        if artifact.artifact_type in {
            RenderArtifactType.SCENE_VIDEO,
            RenderArtifactType.LONG_FORM_VIDEO,
            RenderArtifactType.SHORT_FORM_VIDEO,
        } and exists:
            try:
                probe = self.runner.probe(artifact.path)
                expected_width = artifact.width
                expected_height = artifact.height
                duration_ok = (
                    probe.duration_seconds <= manifest.settings.maximum_render_duration_seconds + 5
                    if artifact.artifact_type != RenderArtifactType.SCENE_VIDEO
                    else probe.duration_seconds > 0
                )
                dimensions_ok = (
                    probe.width == expected_width and probe.height == expected_height
                )
                checks.extend(
                    [
                        self._check(
                            f"Video stream: {artifact.artifact_id}",
                            probe.has_video,
                            "Expected video stream exists.",
                            "Expected video stream is missing.",
                        ),
                        self._check(
                            f"Dimensions: {artifact.artifact_id}",
                            dimensions_ok,
                            "Video dimensions match the manifest.",
                            "Video dimensions do not match the manifest.",
                        ),
                        self._check(
                            f"Duration: {artifact.artifact_id}",
                            duration_ok,
                            "Video duration is within the pilot limit.",
                            "Video duration exceeds the pilot limit.",
                        ),
                    ]
                )
                if artifact.artifact_type != RenderArtifactType.SCENE_VIDEO:
                    silent_declared = any(
                        "silent" in warning.casefold() for warning in artifact.warnings
                    )
                    checks.append(
                        self._check(
                            f"Audio stream: {artifact.artifact_id}",
                            probe.has_audio or silent_declared,
                            "Audio exists or silent fallback is declared.",
                            "Audio is missing without a silent-fallback declaration.",
                        )
                    )
            except Exception:
                checks.append(
                    self._check(
                        f"Probe: {artifact.artifact_id}",
                        False,
                        "Video is probeable.",
                        "Video could not be probed.",
                    )
                )
        if artifact.artifact_type == RenderArtifactType.THUMBNAIL:
            checks.append(
                self._check(
                    f"Thumbnail dimensions: {artifact.artifact_id}",
                    artifact.width == 1280 and artifact.height == 720,
                    "Thumbnail dimensions are 1280x720.",
                    "Thumbnail dimensions are not 1280x720.",
                )
            )
        return checks

    @staticmethod
    def _check(name: str, passed: bool, success: str, failure: str) -> RenderValidationCheck:
        return RenderValidationCheck(
            name=name,
            passed=passed,
            blocking=True,
            message=success if passed else failure,
        )
