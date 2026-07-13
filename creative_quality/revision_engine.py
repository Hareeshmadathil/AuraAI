"""Bounded, copy-based deterministic production revision."""

from __future__ import annotations

from core import TaskPriority
from creative_quality.models import (
    CreativeQualityIssue,
    CreativeQualityPackage,
    QualityDimension,
    QualitySeverity,
    RevisionAction,
    RevisionPlan,
)
from production.models import ProductionPackage, SubtitleSegment


class DeterministicRevisionEngine:
    """Apply safe editorial changes while preserving evidence and originals."""

    def __init__(self, maximum_revision_count: int = 1) -> None:
        if maximum_revision_count < 1:
            raise ValueError("Maximum revision count must be at least one.")
        self.maximum_revision_count = maximum_revision_count

    def create_plan(
        self,
        issues: list[CreativeQualityIssue],
        *,
        revision_count: int = 0,
    ) -> RevisionPlan:
        """Convert findings into one auditable mandatory/optional plan."""

        if revision_count >= self.maximum_revision_count:
            raise ValueError("Maximum deterministic revision count reached.")
        actions: list[RevisionAction] = []
        for issue in issues:
            actions.append(
                RevisionAction(
                    priority=(
                        TaskPriority.CRITICAL
                        if issue.blocking
                        else TaskPriority.HIGH
                        if issue.severity in {
                            QualitySeverity.HIGH,
                            QualitySeverity.MEDIUM,
                        }
                        else TaskPriority.NORMAL
                    ),
                    dimension=issue.dimension,
                    target_reference=issue.affected_reference,
                    instruction=issue.remediation or issue.description,
                    expected_improvement=(
                        f"Improve {issue.dimension.value.replace('_', ' ')} "
                        "without changing supplied facts or evidence."
                    ),
                    requires_human_review=issue.dimension
                    in {QualityDimension.FACTUALITY, QualityDimension.TRUST},
                )
            )
        mandatory = [
            action.action_id
            for action, issue in zip(actions, issues, strict=True)
            if issue.blocking
            or issue.severity in {QualitySeverity.HIGH, QualitySeverity.MEDIUM}
        ]
        optional = [
            action.action_id for action in actions if action.action_id not in mandatory
        ]
        return RevisionPlan(
            actions=actions,
            estimated_quality_gain=min(15.0, len(actions) * 2.5),
            mandatory_actions=mandatory,
            optional_actions=optional,
            revision_count=revision_count + 1,
        )

    def revise(
        self,
        package: ProductionPackage,
        quality: CreativeQualityPackage,
        *,
        revision_count: int = 0,
    ) -> tuple[ProductionPackage, RevisionPlan, list[str]]:
        """Return a revised deep copy and leave the original untouched."""

        plan = self.create_plan(quality.issues, revision_count=revision_count)
        revised = package.model_copy(deep=True)
        applied: list[str] = []

        if quality.hook_analysis.improved_hook != revised.script.hook:
            revised.script = revised.script.model_copy(
                update={"hook": quality.hook_analysis.improved_hook}
            )
            applied.append("Updated the opening hook with the reviewed truthful hook.")

        revised_sections = []
        for section in revised.script.sections:
            device = section.retention_device
            if "viewer question" not in device.lower():
                device = f"{device}; bridge to the next viewer question"
            revised_sections.append(
                section.model_copy(update={"retention_device": device})
            )
        revised.script = revised.script.model_copy(
            update={
                "sections": revised_sections,
                "call_to_action": (
                    f"At approximately "
                    f"{quality.retention_report.call_to_action_timing:.0f}s: "
                    f"{revised.script.call_to_action}"
                ),
            }
        )
        applied.append(
            "Added viewer-question bridges and explicit call-to-action timing."
        )

        scenes = [
            scene.model_copy(
                update={"transition": "Evidence-led bridge to the next viewer question"}
            )
            for scene in revised.storyboard.scenes
        ]
        revised.storyboard = revised.storyboard.model_copy(update={"scenes": scenes})
        applied.append("Standardized restrained evidence-led storyboard transitions.")

        motion_by_scene = {
            cue.scene_id: cue.instructions for cue in quality.motion_plan.cues
        }
        track_items = [
            item.model_copy(
                update={
                    "instructions": (
                        f"{item.instructions} Motion guidance: "
                        f"{motion_by_scene[item.scene_id]}"
                    )[:3000]
                }
            )
            if item.scene_id in motion_by_scene
            else item
            for item in revised.assembly_manifest.track_items
        ]
        revised.assembly_manifest = revised.assembly_manifest.model_copy(
            update={"track_items": track_items}
        )
        applied.append("Added deterministic motion guidance to assembly instructions.")

        optimized = quality.subtitle_optimization
        segments = [
            SubtitleSegment(
                index=source.index,
                start_seconds=source.start_seconds,
                end_seconds=source.end_seconds,
                text=analysis.optimized_text,
            )
            for source, analysis in zip(
                revised.subtitle_package.segments,
                optimized.lines,
                strict=True,
            )
        ]
        revised.subtitle_package = revised.subtitle_package.model_copy(
            update={
                "segments": segments,
                "srt_text": optimized.optimized_srt_text,
                "vtt_text": optimized.optimized_vtt_text,
            }
        )
        applied.append("Applied mobile-readable in-memory subtitle formatting.")

        revised.thumbnail_plan = revised.thumbnail_plan.model_copy(
            update={
                "recommended_concept_id": (
                    quality.thumbnail_report.recommended_concept_id
                )
            }
        )
        applied.append("Updated the recommended truthful thumbnail concept.")
        revised.warnings = list(
            dict.fromkeys(
                [
                    *revised.warnings,
                    *quality.factuality_report.disclaimer_requirements,
                    "Creative Quality revisions do not verify external facts.",
                ]
            )
        )
        completed_actions = [
            action.model_copy(
                update={
                    "completed": not action.requires_human_review,
                }
            )
            for action in plan.actions
        ]
        plan = plan.model_copy(update={"actions": completed_actions})
        return ProductionPackage.model_validate(revised), plan, applied
