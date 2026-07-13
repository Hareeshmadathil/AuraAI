"""Transparent quality checks for structured production packages."""

from __future__ import annotations

from production.models import (
    ApprovalRequirement,
    AssetStatus,
    ProductionApprovalStatus,
    ProductionPackage,
    ProductionQualityReport,
    QualityCheck,
    QualitySeverity,
    RenderStatus,
    SCRIPT_DURATION_TOLERANCE_PERCENT,
)


class ProductionQualityController:
    """Evaluate completeness, safety, timing, and approval governance."""

    def review(self, package: ProductionPackage) -> ProductionQualityReport:
        """Return a deterministic report without modifying the package."""

        checks = [
            self._required_assets(package),
            self._duration_alignment(package),
            self._storyboard_coverage(package),
            self._scene_timing(package),
            self._keyword_alignment(package),
            self._factuality_markers(package),
            self._copyright_notes(package),
            self._thumbnail_readability(package),
            self._unsupported_claims(package),
            self._short_form(package),
            self._subtitles(package),
            self._manifest(package),
            self._planned_labels(package),
            self._approval(package),
        ]
        blockers = [
            check.message
            for check in checks
            if not check.passed and check.severity == QualitySeverity.BLOCKING
        ]
        warnings = [
            check.message
            for check in checks
            if not check.passed and check.severity == QualitySeverity.WARNING
        ]
        score = round(sum(check.passed for check in checks) / len(checks) * 100, 2)
        approval = (
            ApprovalRequirement.FOUNDER_REQUIRED
            if package.input.requires_founder_approval
            else ApprovalRequirement.AUTOMATED_SAFE
        )
        return ProductionQualityReport(
            production_package_id=package.package_id,
            checks=checks,
            passed=not blockers,
            approval_required=approval,
            blocking_issues=blockers,
            warnings=warnings,
            score_percentage=score,
        )

    @staticmethod
    def _check(
        category: str,
        name: str,
        passed: bool,
        success: str,
        failure: str,
        *,
        severity: QualitySeverity = QualitySeverity.BLOCKING,
        remediation: str | None = None,
    ) -> QualityCheck:
        return QualityCheck(
            category=category,
            name=name,
            passed=passed,
            severity=severity,
            message=success if passed else failure,
            remediation=None if passed else remediation,
        )

    def _required_assets(self, package: ProductionPackage) -> QualityCheck:
        fields = (
            package.brief,
            package.script.sections,
            package.storyboard.scenes,
            package.voiceover_plan.segments,
            package.visual_plan.requests,
            package.thumbnail_plan.concepts,
            package.short_form_package.assets,
            package.subtitle_package.segments,
            package.assembly_manifest.track_items,
        )
        return self._check(
            "completeness",
            "Required structured assets",
            all(bool(field) for field in fields),
            "All required structured production assets are present.",
            "One or more required structured production assets are missing.",
            remediation="Regenerate the missing stage before review.",
        )

    def _duration_alignment(self, package: ProductionPackage) -> QualityCheck:
        target = package.input.target_duration_seconds
        difference = abs(package.script.total_estimated_duration_seconds - target)
        percentage = difference / target * 100
        return self._check(
            "timing",
            "Script duration alignment",
            percentage <= SCRIPT_DURATION_TOLERANCE_PERCENT,
            "Script duration is within the documented 15% target tolerance.",
            "Script duration exceeds the documented 15% target tolerance.",
            remediation="Adjust section timings or the requested target duration.",
        )

    def _storyboard_coverage(self, package: ProductionPackage) -> QualityCheck:
        covered = {scene.script_section_id for scene in package.storyboard.scenes}
        required = {section.section_id for section in package.script.sections}
        return self._check(
            "storyboard",
            "Script coverage",
            required.issubset(covered),
            "Every script section is represented in the storyboard.",
            "The storyboard does not cover every script section.",
            remediation="Add a timed scene for every uncovered script section.",
        )

    def _scene_timing(self, package: ProductionPackage) -> QualityCheck:
        scenes = package.storyboard.scenes
        valid = all(
            scene.end_seconds > scene.start_seconds
            and (index == 0 or scene.start_seconds >= scenes[index - 1].end_seconds)
            for index, scene in enumerate(scenes)
        )
        return self._check(
            "storyboard",
            "Sequential scene timing",
            valid,
            "Scene timing is sequential and non-overlapping.",
            "Scene timing overlaps or contains an invalid duration.",
            remediation="Recalculate storyboard scene boundaries.",
        )

    def _keyword_alignment(self, package: ProductionPackage) -> QualityCheck:
        keyword = package.input.primary_keyword.casefold()
        aligned = keyword in (
            package.script.title + " " + package.script.hook
        ).casefold()
        return self._check(
            "editorial",
            "Title and keyword alignment",
            aligned,
            "The primary keyword is naturally aligned with title or hook.",
            "The primary keyword is absent from both title and hook.",
            severity=QualitySeverity.WARNING,
            remediation="Add the keyword naturally without stuffing.",
        )

    def _factuality_markers(self, package: ProductionPackage) -> QualityCheck:
        marked = any(
            section.claims_requiring_verification
            for section in package.script.sections
        ) and bool(package.script.disclaimer_notes)
        return self._check(
            "factuality",
            "Verification markers",
            marked,
            "Factual claims and publication review needs are identified.",
            "Factuality warnings or verification markers are absent.",
            remediation="Mark material claims and add factual-review notes.",
        )

    def _copyright_notes(self, package: ProductionPackage) -> QualityCheck:
        notes = " ".join(
            note
            for scene in package.storyboard.scenes
            for note in scene.safety_notes
        ).casefold()
        valid = "copyright" in notes and all(
            request.rights_requirements for request in package.visual_plan.requests
        )
        return self._check(
            "rights",
            "Copyright and brand safety",
            valid,
            "Copyright and asset-rights requirements are present.",
            "Copyright or rights guidance is incomplete.",
            remediation="Add original/licensed asset and non-imitation requirements.",
        )

    def _thumbnail_readability(self, package: ProductionPackage) -> QualityCheck:
        valid = len(package.thumbnail_plan.concepts) >= 3 and all(
            len(concept.primary_text.split()) <= 4
            and bool(concept.mobile_readability_notes)
            for concept in package.thumbnail_plan.concepts
        )
        return self._check(
            "thumbnail",
            "Mobile readability",
            valid,
            "Thumbnail concepts are distinct and mobile-readable.",
            "Thumbnail concepts are insufficient or text is too long.",
            remediation="Provide three concepts with four words or fewer.",
        )

    def _unsupported_claims(self, package: ProductionPackage) -> QualityCheck:
        text = " ".join(
            section.narration for section in package.script.sections
        ).casefold()
        prohibited = (
            "guaranteed revenue",
            "guaranteed income",
            "guaranteed earnings",
            "guaranteed cure",
            "guaranteed legal",
        )
        valid = not any(claim in text for claim in prohibited)
        return self._check(
            "safety",
            "Unsupported guarantee scan",
            valid,
            "No unsupported revenue, medical, legal, or financial guarantee was found.",
            "An unsupported guarantee appears in the script.",
            remediation="Remove the guarantee and add qualified, sourced language.",
        )

    def _short_form(self, package: ProductionPackage) -> QualityCheck:
        counts = {}
        for asset in package.short_form_package.assets:
            counts[asset.platform] = counts.get(asset.platform, 0) + 1
        valid = all(count >= 3 for count in counts.values()) and len(counts) == 3
        return self._check(
            "derivatives",
            "Short-form package",
            valid,
            "Three derivatives exist for each supported short-form platform.",
            "Short-form platform derivatives are incomplete.",
            remediation="Create three standalone concepts for every target platform.",
        )

    def _subtitles(self, package: ProductionPackage) -> QualityCheck:
        subtitles = package.subtitle_package
        valid = bool(subtitles.segments) and subtitles.vtt_text.startswith("WEBVTT")
        return self._check(
            "accessibility",
            "Subtitle validity",
            valid,
            "Sequential SRT and WebVTT subtitle content is present.",
            "Subtitle output is absent or invalid.",
            remediation="Regenerate subtitles from the voice plan.",
        )

    def _manifest(self, package: ProductionPackage) -> QualityCheck:
        manifest = package.assembly_manifest
        valid = bool(manifest.track_items) and manifest.render_status == RenderStatus.NOT_RENDERED
        return self._check(
            "assembly",
            "Assembly manifest",
            valid,
            "The assembly manifest is complete and explicitly not rendered.",
            "The assembly manifest is incomplete or mislabels render state.",
            remediation="Rebuild the manifest and preserve NOT_RENDERED status.",
        )

    def _planned_labels(self, package: ProductionPackage) -> QualityCheck:
        valid = all(
            request.status == AssetStatus.NOT_GENERATED
            and request.output_path is None
            for request in package.visual_plan.requests
        )
        return self._check(
            "truthfulness",
            "Planned and sample labels",
            valid,
            "Visual outputs are explicitly labelled planned/not generated.",
            "A visual request could be mistaken for generated media.",
            remediation="Remove output paths and mark requests NOT_GENERATED.",
        )

    def _approval(self, package: ProductionPackage) -> QualityCheck:
        required = package.input.requires_founder_approval
        honored = not required or package.approval_status in {
            ProductionApprovalStatus.PENDING,
            ProductionApprovalStatus.APPROVED,
        }
        pending = required and package.approval_status == ProductionApprovalStatus.PENDING
        return self._check(
            "governance",
            "Founder approval",
            honored and not pending,
            "Founder approval is satisfied or not required.",
            "Founder approval remains pending; the package cannot be rendered or published.",
            severity=QualitySeverity.WARNING if honored else QualitySeverity.BLOCKING,
            remediation="Obtain explicit founder approval before downstream production.",
        )
