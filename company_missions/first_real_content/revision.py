"""One bounded, deterministic founder revision for AuraAI Mission Zero."""

from __future__ import annotations

from typing import Any

from core import ApprovalStatus, ValidationError, utc_now
from creative_quality.intelligence import CreativeQualityIntelligence
from creative_quality.models import (
    CreativeQualityPackage,
    CreativeQualityPipelineResult,
    QualityDepartment,
)
from mission_engine import (
    MissionArtifact,
    MissionArtifactType,
    MissionExecutionStatus,
    MissionHistoryEntry,
)
from production.models import (
    ProductionApprovalStatus,
    ProductionPackage,
    ProductionPipelineResult,
    RenderStatus,
    ScriptSection,
    VideoScript,
)
from production.revision_subtitle_engine import ControlledRevisionSubtitleEngine

from company_missions.first_real_content.models import (
    ArtifactVersionSummary,
    DepartmentQualityComparison,
    FirstContentMissionInput,
    FirstContentMissionResult,
    MissionSummary,
    ProductionReviewPackage,
    QualityRevisionComparison,
)
from company_missions.real_content_pilot.artifacts import (
    CreativeQualityArtifact,
    FounderReviewArtifact,
    FounderReviewStatus,
    ProductionPackageArtifact,
    RevisionRequestArtifact,
    ScriptArtifact,
)


REVISION_OBJECTIVES = (
    "Replace the generic opening with a specific, truthful AuraAI tension.",
    "Rebuild the story as a nine-step transformation with evidence-led transitions.",
    "Shorten sections and add distinct proof moments and pattern interrupts.",
    "Regenerate synchronized subtitles within 42 characters, two lines, and 20 CPS.",
)


class MissionZeroRevisionEngine:
    """Build a truthful script-v2 solely from founder-supplied evidence."""

    def build(
        self,
        result: FirstContentMissionResult,
        value: FirstContentMissionInput,
    ) -> VideoScript:
        """Return the controlled nine-part Mission Zero transformation story."""

        evidence = self._evidence_notes(value)
        specs = self._section_specs(value)
        sections = [
            ScriptSection(
                section_type=section_type,
                title=title,
                purpose=purpose,
                narration=narration,
                estimated_duration_seconds=duration,
                visual_intent=visual,
                retention_device=retention,
                source_notes=evidence,
                claims_requiring_verification=claims,
            )
            for (
                section_type,
                title,
                purpose,
                narration,
                duration,
                visual,
                retention,
                claims,
            ) in specs
        ]
        word_count = sum(len(section.narration.split()) for section in sections)
        return VideoScript(
            brief_id=result.production_package.brief.brief_id,
            title="I Built an AI Media Company—Here Is What Actually Works",
            hook=(
                "AuraAI now runs content missions, scores its work, and stops "
                "before publishing. The harder problem was making it worth watching."
            ),
            sections=sections,
            call_to_action=value.primary_call_to_action,
            total_estimated_duration_seconds=sum(
                section.estimated_duration_seconds for section in sections
            ),
            word_count=word_count,
            primary_keyword=result.production_package.script.primary_keyword,
            secondary_keywords=list(
                result.production_package.script.secondary_keywords
            ),
            disclaimer_notes=list(
                result.production_package.script.disclaimer_notes
            ),
            sample_data=value.sample_data,
        )

    @staticmethod
    def _evidence_notes(value: FirstContentMissionInput) -> list[str]:
        preserved = [
            note
            for note in value.source_notes
            if "360 passing automated tests" not in note
        ]
        return [
            *preserved,
            *value.source_references,
            "Founder revision instruction and the local 369-test result.",
            "Repository history, dashboard, and exported Mission Zero artifacts.",
        ]

    @staticmethod
    def _section_specs(
        value: FirstContentMissionInput,
    ) -> list[tuple[str, str, str, str, float, str, str, list[str]]]:
        return [
            (
                "hook",
                "The harder problem",
                "Show the current result and open the central tension.",
                "I started AuraAI as a transcript-processing script. Today, the "
                "same Python project coordinates specialized AI roles, runs a "
                "content mission, scores the result, and stops before publishing "
                "until I make a decision. Mission Zero exposed the harder problem: "
                "more automation does not automatically create something people "
                "would choose to watch. In this video, I will show the architecture, "
                "the failures that changed it, and the exact founder gate that keeps "
                "rendering and publishing separate.",
                45.0,
                "Open on the dashboard, then show the founder-review stop state.",
                "Open loop: why did a working system still produce a weak story?",
                [
                    "AuraAI began as a transcript-processing script.",
                    "AuraAI stops content missions at founder review.",
                ],
            ),
            (
                "origin",
                "The first simple version",
                "Explain the narrow starting point before the company structure.",
                "The first version solved one narrow problem: take transcript text "
                "and process it through a repeatable Python workflow. That was useful "
                "because the input and output were easy to inspect. It also established "
                "the rule that still matters now: automation should produce a reviewable "
                "artifact, not an invisible decision. On screen, the early code and Git "
                "history provide the proof. But a single script could not plan a mission, "
                "coordinate specialist roles, or explain why one draft was stronger than "
                "another. That limitation created the next question: what structure was missing?",
                55.0,
                "Show the early transcript workflow beside its Git history.",
                "Proof contrast: one script versus a complete mission workflow.",
                ["AuraAI began with a narrow transcript-processing workflow."],
            ),
            (
                "problem",
                "Why one script was insufficient",
                "Resolve the first limitation and establish the need for coordination.",
                "Content work is not one task. Research, search intent, scripting, "
                "production planning, quality review, and distribution controls depend "
                "on different inputs and safeguards. Combining them inside one large "
                "function would make failures difficult to locate and decisions difficult "
                "to audit. The first Mission Zero draft proved the point. It was complete "
                "enough to review, yet its hook, story, retention, and subtitles were weak. "
                "The Creative Quality breakdown made those weaknesses visible instead of "
                "hiding them behind a successful pipeline run.",
                55.0,
                "Reveal the original 72.52 quality breakdown department by department.",
                "Pattern interrupt: replace the architecture view with the failed scorecard.",
                ["The original Mission Zero Creative Quality score was 72.52."],
            ),
            (
                "architecture",
                "Building the company structure",
                "Show how specialized roles and mission artifacts solve coordination.",
                "AuraAI now organizes work through a CEO, a COO, department directors, "
                "specialists, tasks, workflows, and typed mission artifacts. The labels "
                "describe software roles, not human employees. A Mission Manager records "
                "state transitions and artifact versions. Production creates structured "
                "plans without rendering media. Creative Quality reviews the package "
                "before any delivery decision. The dashboard then projects the same runtime "
                "state for the founder. This structure does not remove human responsibility; "
                "it makes responsibility and handoffs easier to see.",
                60.0,
                "Animate the repository architecture from mission to versioned artifacts.",
                "Visual proof: trace one artifact through the dashboard and mission history.",
                [
                    "AuraAI uses specialized software roles and typed mission artifacts.",
                    "Production planning remains separate from rendering.",
                ],
            ),
            (
                "failures",
                "Failures that changed the system",
                "Use concrete engineering failures before explaining safeguards.",
                "The safeguards were shaped by real failures. Gemini connectivity reached "
                "the API, but request-format and timeout problems required transport fixes "
                "and deterministic fallback. Later, one forty-three-character subtitle line "
                "failed a strict forty-two-character validator and stopped Mission Zero. "
                "The correction wrapped subtitle text before validation rather than weakening "
                "the rule. The local suite now reports 369 passing tests. Git history shows "
                "these corrections as separate checkpoints. Each failure reinforced the same "
                "principle: keep the boundary strict, make the failure diagnosable, and preserve "
                "the founder's ability to stop the workflow.",
                65.0,
                "Cut between safe Gemini diagnostics, the subtitle regression, and tests.",
                "Failure montage: transport, subtitle validator, then the green test result.",
                [
                    "Gemini connectivity was verified in a founder-approved smoke test.",
                    "A 43-character subtitle line previously failed the 42-character validator.",
                    "The local automated test suite reports 369 passing tests.",
                ],
            ),
            (
                "demonstration",
                "Mission Zero working today",
                "Resolve the early curiosity loop with the current controlled workflow.",
                "Mission Zero begins with founder-supplied facts and constraints. Research "
                "and SEO artifacts remain versioned. Production prepares a script, storyboard, "
                "voice plan, subtitles, thumbnail direction, and a non-rendered assembly "
                "manifest. Creative Quality scores seven founder-facing departments and lists "
                "the responsible specialist for each recommendation. The first review scored "
                "72.52 and requested a founder decision. This revised run preserves script v1, "
                "creates script v2, reruns the same quality pipeline, and returns to founder "
                "review. That is the concrete payoff: the system can revise without erasing "
                "what happened before.",
                65.0,
                "Walk through the terminal mission run and both script versions.",
                "Resolve the opening loop with the version lineage and revised score.",
                [
                    "Mission Zero preserves versioned research, SEO, script, and quality artifacts.",
                    "The original Mission Zero review scored 72.52.",
                ],
            ),
            (
                "limitations",
                "What still does not work",
                "State current limits next to the working demonstration.",
                "AuraAI is not a fully autonomous company, and its AI roles are not people. "
                "It does not prove that a video will earn views, subscribers, customers, or "
                "revenue. A quality score is an internal engineering heuristic, not an audience "
                "forecast. Live provider output still needs validation and can fall back to "
                "deterministic behavior. Rendering remains a separate approval boundary, and "
                "publishing remains separately controlled. Those limits are not footnotes. "
                "They are part of the product definition and the reason this mission stops here.",
                60.0,
                "Hold on explicit NOT RENDERED and NOT PUBLISHED labels.",
                "Credibility reset: separate demonstrated behavior from future capability.",
                [
                    "Rendering and publishing remain separately controlled.",
                    "Creative Quality scores are internal deterministic heuristics.",
                ],
            ),
            (
                "roadmap",
                "What comes next",
                "Connect current limits to the next controlled engineering work.",
                "The next work is not to remove every gate. It is to improve the evidence "
                "flow between missions, make founder comparisons clearer, and test each local "
                "production stage with real review data. Future rendering can proceed only "
                "after an explicit content decision and a separate render approval. Publishing "
                "will remain another controlled step. Building in public means showing those "
                "boundaries, the failures behind them, and the code changes that make the system "
                "more reliable—without pretending the roadmap is already complete.",
                60.0,
                "Show the roadmap as gated steps rather than an autonomy claim.",
                "Forward question: which controlled boundary should be tested next?",
                ["Rendering and publishing require separate controlled decisions."],
            ),
            (
                "conclusion",
                "Follow the build in public",
                "Invite viewers after resolving the transformation and its limits.",
                "AuraAI moved from one transcript script to a founder-controlled media "
                "operating system with specialized roles, versioned missions, deterministic "
                "fallback, quality review, and explicit stop points. Mission Zero also showed "
                "that working software is not the same as a compelling story, which is why "
                "this revision exists. If you want to see the next failures, fixes, and honest "
                "tradeoffs, subscribe and follow the journey as AuraAI develops from a local "
                "project into a functioning AI media company.",
                45.0,
                "Return to the dashboard and the pending founder decision.",
                "Viewer invitation: follow the next measured build checkpoint.",
                ["AuraAI remains a founder-controlled local project."],
            ),
        ]


class MissionZeroRevisionService:
    """Execute exactly one founder-requested revision on the existing mission."""

    def __init__(self, runner: Any) -> None:
        self._runner = runner
        self._engine = MissionZeroRevisionEngine()

    def execute(
        self,
        requested: FirstContentMissionResult,
        value: FirstContentMissionInput,
        notes: str,
    ) -> FirstContentMissionResult:
        """Create script-v2, rerun production and quality, and return to review."""

        if requested.revision_request is not None or len(requested.script_versions) > 1:
            raise ValidationError(
                "The Mission Zero revision limit has been reached.",
                error_code="PILOT_REVISION_LIMIT_REACHED",
            )
        if requested.mission.status != MissionExecutionStatus.FOUNDER_REVIEW:
            raise ValidationError(
                "Mission Zero must be in founder review before revision.",
                error_code="MISSION_NOT_IN_FOUNDER_REVIEW",
            )
        request = RevisionRequestArtifact(
            mission_id=requested.mission.mission_id,
            notes=notes,
            objectives=list(REVISION_OBJECTIVES),
        )
        self._register(
            request,
            MissionArtifactType.REVISION_REQUEST,
            "Founder",
            "Founder requested one controlled Mission Zero revision.",
        )
        script_draft = self._engine.build(requested, value)
        production = self._run_production(requested, script_draft)
        revised_quality = self._run_quality(production)
        comparison = self._comparison(
            requested.creative_quality_package,
            revised_quality,
        )
        self._validate_revision(production, revised_quality, comparison)
        return self._finalize(
            requested,
            value,
            request,
            production,
            revised_quality,
            comparison,
        )

    def _run_production(
        self,
        requested: FirstContentMissionResult,
        script: VideoScript,
    ) -> ProductionPackage:
        operation = self._runner.pilot.production_pipeline.run(
            requested.production_package.input,
            founder_approved=False,
            controlled_script_revision=script,
            preserved_thumbnail_plan=requested.production_package.thumbnail_plan,
            controlled_subtitle_engine=ControlledRevisionSubtitleEngine(),
        )
        if not operation.success:
            raise ValidationError(
                operation.message,
                error_code=operation.error_code or "REVISION_PRODUCTION_FAILED",
            )
        result = ProductionPipelineResult.model_validate(
            operation.data["production_pipeline_result"]
        )
        return result.package

    def _run_quality(self, package: ProductionPackage) -> CreativeQualityPackage:
        operation = self._runner.pilot.quality_pipeline.run(
            package,
            founder_quality_override=False,
        )
        data = operation.data.get("creative_quality_pipeline_result")
        if data is None:
            raise ValidationError(
                operation.message,
                error_code=operation.error_code or "REVISION_QUALITY_FAILED",
            )
        result = CreativeQualityPipelineResult.model_validate(data)
        if result.revised_production_package is not None:
            raise ValidationError(
                "The revised package requested an additional automatic revision.",
                error_code="SECOND_REVISION_NOT_ALLOWED",
            )
        return result.quality_package

    @staticmethod
    def _comparison(
        original: CreativeQualityPackage,
        revised: CreativeQualityPackage,
    ) -> QualityRevisionComparison:
        intelligence = CreativeQualityIntelligence()
        original_report = original.quality_breakdown or intelligence.build(original)
        revised_report = revised.quality_breakdown or intelligence.build(revised)
        original_departments = {
            item.department: item for item in original_report.departments
        }
        revised_departments = {
            item.department: item for item in revised_report.departments
        }
        departments = [
            DepartmentQualityComparison(
                department=department,
                original_score=original_departments[department].score,
                revised_score=revised_departments[department].score,
                change=round(
                    revised_departments[department].score
                    - original_departments[department].score,
                    2,
                ),
            )
            for department in QualityDepartment
        ]
        return QualityRevisionComparison(
            original_overall_score=original.scores.overall,
            revised_overall_score=revised.scores.overall,
            overall_change=round(
                revised.scores.overall - original.scores.overall,
                2,
            ),
            departments=departments,
            original_blocker_count=len(original.gate.blocking_issues),
            revised_blocker_count=len(revised.gate.blocking_issues),
        )

    @staticmethod
    def _validate_revision(
        production: ProductionPackage,
        quality: CreativeQualityPackage,
        comparison: QualityRevisionComparison,
    ) -> None:
        changes = {item.department: item.change for item in comparison.departments}
        weak = {
            QualityDepartment.HOOK,
            QualityDepartment.STORY,
            QualityDepartment.RETENTION,
            QualityDepartment.SUBTITLES,
        }
        if any(changes[department] <= 0 for department in weak):
            raise ValidationError(
                "The controlled revision did not improve every weak department.",
                error_code="REVISION_OBJECTIVE_NOT_MET",
            )
        if quality.gate.blocking_issues:
            raise ValidationError(
                "The controlled revision introduced a quality blocker.",
                error_code="REVISION_INTRODUCED_BLOCKER",
            )
        lines = quality.subtitle_optimization.lines
        if any(
            line.characters_per_line > 42
            or line.line_count > 2
            or line.reading_speed_cps > 20
            for line in lines
        ):
            raise ValidationError(
                "Revised subtitles do not meet the founder readability constraints.",
                error_code="REVISION_SUBTITLE_CONSTRAINT_FAILED",
            )
        if production.approval_status != ProductionApprovalStatus.PENDING:
            raise ValidationError(
                "Revised production must remain pending founder approval.",
                error_code="REVISION_APPROVAL_BYPASS",
            )
        if production.assembly_manifest.render_status != RenderStatus.NOT_RENDERED:
            raise ValidationError(
                "Revised production cannot be rendered.",
                error_code="REVISION_RENDER_BYPASS",
            )

    def _finalize(
        self,
        original: FirstContentMissionResult,
        value: FirstContentMissionInput,
        request: RevisionRequestArtifact,
        production: ProductionPackage,
        quality: CreativeQualityPackage,
        comparison: QualityRevisionComparison,
    ) -> FirstContentMissionResult:
        script_v1 = original.script_versions[0]
        script_v1_metadata = self._mission_artifact_for_typed(
            script_v1.artifact_id
        )
        script_v2 = self._script_artifact(
            original,
            production.script,
            script_v1,
        )
        self._register(
            script_v2,
            MissionArtifactType.SCRIPT,
            self._runner.pilot.production_pipeline.script_writer.name,
            "Mission Zero script-v2 after one founder-requested revision.",
            parent_artifact_id=script_v1_metadata.artifact_id,
        )
        original_production = self._production_artifact(
            original.mission.mission_id,
            original.production_package,
            version=1,
        )
        original_production_metadata = self._register(
            original_production,
            MissionArtifactType.PRODUCTION_PACKAGE,
            self._runner.pilot.production_pipeline.production_director.name,
            "Original review-only Mission Zero production package.",
        )
        revised_production = self._production_artifact(
            original.mission.mission_id,
            production,
            version=2,
            parent_artifact_id=original_production.artifact_id,
        )
        self._register(
            revised_production,
            MissionArtifactType.PRODUCTION_PACKAGE,
            self._runner.pilot.production_pipeline.production_director.name,
            "Revised review-only Mission Zero production package.",
            parent_artifact_id=original_production_metadata.artifact_id,
        )
        quality_v1_metadata = self._mission_artifact_for_typed(
            original.pilot.quality_artifact.artifact_id
        )
        quality_v2 = CreativeQualityArtifact(
            mission_id=original.mission.mission_id,
            version_number=2,
            parent_artifact_id=original.pilot.quality_artifact.artifact_id,
            quality_package_id=quality.package_id,
            overall_score=quality.scores.overall,
            gate_status=quality.gate.status,
            blocking_issues=[
                issue.description for issue in quality.gate.blocking_issues
            ],
            warnings=list(quality.gate.warnings),
            revision_count=1,
            founder_override_allowed=quality.gate.founder_override_allowed,
        )
        self._register(
            quality_v2,
            MissionArtifactType.QUALITY_REPORT,
            self._runner.pilot.quality_pipeline.creative_director.name,
            f"Revised Creative Quality score {quality.scores.overall}.",
            parent_artifact_id=quality_v1_metadata.artifact_id,
        )
        review_v1_metadata = self._mission_artifact_for_typed(
            original.pilot.founder_review_artifact.artifact_id
        )
        review_v2 = FounderReviewArtifact(
            mission_id=original.mission.mission_id,
            version_number=2,
            parent_artifact_id=original.pilot.founder_review_artifact.artifact_id,
            review_status=FounderReviewStatus.PENDING,
            research_summary=original.pilot.research_artifact.executive_summary,
            seo_summary=original.pilot.founder_review_artifact.seo_summary,
            script_summary=(
                f"{production.script.title}; {len(production.script.sections)} "
                f"sections; {production.script.word_count} words; script-v2."
            ),
            quality_summary=(
                f"Original {comparison.original_overall_score}; revised "
                f"{comparison.revised_overall_score}; gate {quality.gate.status.value}."
            ),
            blocking_items=quality_v2.blocking_issues,
            recommended_action=(
                "Founder must review script-v2 and the score comparison; "
                "rendering and publishing remain unapproved."
            ),
        )
        self._register(
            review_v2,
            MissionArtifactType.APPROVAL_NOTES,
            "Aura",
            "Updated founder-review package after controlled revision.",
            parent_artifact_id=review_v1_metadata.artifact_id,
        )
        mission = self._record_completion(original.mission.mission_id, comparison)
        pilot = original.pilot.model_copy(
            update={
                "mission": mission,
                "quality_artifact": quality_v2,
                "founder_review_artifact": review_v2,
                "production_package": production,
                "creative_quality_package": quality,
                "script_versions": [script_v1, script_v2],
            }
        )
        threshold_blockers = [
            issue.description for issue in quality.gate.blocking_issues
        ]
        if quality.scores.overall < value.founder_quality_threshold:
            threshold_blockers.append(
                "Revised Creative Quality score is below the founder-defined threshold."
            )
        founder_review = original.founder_review.model_copy(
            update={
                "recommended_title": production.script.title,
                "script_hook": production.script.hook,
                "section_list": [section.title for section in production.script.sections],
                "word_count": production.script.word_count,
                "estimated_duration_seconds": (
                    production.script.total_estimated_duration_seconds
                ),
                "quality_score": quality.scores.overall,
                "gate_status": quality.gate.status.value,
                "revision_history": ["Script v1", "Script v2"],
                "blocking_issues": threshold_blockers,
                "founder_decisions_required": [
                    "Review script-v2 and the comparison, then approve, reject, or stop."
                ],
                "rendered": False,
                "published": False,
            }
        )
        revised = original.model_copy(
            update={
                "mission_summary": self._mission_summary(mission),
                "mission": mission,
                "pilot": pilot,
                "production_package": production,
                "creative_quality_package": quality,
                "script_versions": [script_v1, script_v2],
                "founder_review": founder_review,
                "metadata_review": original.metadata_review.model_copy(
                    update={"title": production.script.title}
                ),
                "production_review": ProductionReviewPackage(
                    package_id=production.package_id,
                    script_versions=2,
                    quality_score=quality.scores.overall,
                    blocking_issues=threshold_blockers,
                    rendered=False,
                    published=False,
                ),
                "revision_request": request,
                "quality_comparison": comparison,
                "production_versions": [
                    *(original.production_versions or [original.production_package]),
                    production,
                ],
                "quality_versions": [
                    *(
                        original.quality_versions
                        or [original.creative_quality_package]
                    ),
                    quality,
                ],
                "export_status": "not_exported",
                "exported_path": None,
                "generated_at": utc_now(),
            }
        )
        payload = {
            name: getattr(revised, name)
            for name in FirstContentMissionResult.model_fields
        }
        return FirstContentMissionResult.model_validate(payload)

    def _register(
        self,
        artifact: Any,
        artifact_type: MissionArtifactType,
        producer: str,
        summary: str,
        *,
        parent_artifact_id: Any = None,
    ) -> MissionArtifact:
        self._runner.pilot.artifact_store.register(artifact)
        mission = self._runner.pilot.mission_manager.load_mission(
            artifact.mission_id
        )
        employee = next(
            (
                item
                for item in mission.assigned_employees
                if item.employee_name == producer
            ),
            None,
        )
        return self._runner.pilot.mission_manager.register_artifact(
            artifact.mission_id,
            artifact_type=artifact_type,
            name=artifact.__class__.__name__,
            summary=summary,
            produced_by_employee_id=(
                employee.employee_id if employee is not None else None
            ),
            producer=producer,
            stage=MissionExecutionStatus.FOUNDER_REVIEW,
            parent_artifact_id=parent_artifact_id,
            metadata_reference=f"memory://pilot/{artifact.artifact_id}",
            metadata={
                "typed_artifact_id": str(artifact.artifact_id),
                "typed_version": artifact.version_number,
            },
        )

    def _mission_artifact_for_typed(self, artifact_id: Any) -> MissionArtifact:
        mission = self._runner.pilot.mission_manager.load_mission(
            self._runner.pilot.last_result.mission.mission_id
        )
        for artifact in mission.produced_artifacts:
            if artifact.metadata.get("typed_artifact_id") == str(artifact_id):
                return artifact
        raise ValidationError(
            "The parent mission artifact was not found.",
            error_code="REVISION_PARENT_ARTIFACT_MISSING",
        )

    @staticmethod
    def _script_artifact(
        original: FirstContentMissionResult,
        script: VideoScript,
        parent: ScriptArtifact,
    ) -> ScriptArtifact:
        return ScriptArtifact(
            mission_id=original.mission.mission_id,
            version_number=2,
            parent_artifact_id=parent.artifact_id,
            title=script.title,
            hook=script.hook,
            sections=[section.narration for section in script.sections],
            call_to_action=script.call_to_action,
            word_count=script.word_count,
            estimated_duration_seconds=script.total_estimated_duration_seconds,
            claims_requiring_verification=[
                claim
                for section in script.sections
                for claim in section.claims_requiring_verification
            ],
            source_notes=parent.source_notes,
            provider_used="deterministic-controlled-revision",
            fallback_used=True,
        )

    @staticmethod
    def _production_artifact(
        mission_id: Any,
        package: ProductionPackage,
        *,
        version: int,
        parent_artifact_id: Any = None,
    ) -> ProductionPackageArtifact:
        return ProductionPackageArtifact(
            mission_id=mission_id,
            version_number=version,
            parent_artifact_id=parent_artifact_id,
            production_package_id=package.package_id,
            script_id=package.script.script_id,
            approval_status=package.approval_status.value,
            render_status=package.assembly_manifest.render_status.value,
            rendered=False,
            published=False,
        )

    def _record_completion(
        self,
        mission_id: Any,
        comparison: QualityRevisionComparison,
    ):
        mission = self._runner.pilot.mission_manager.load_mission(mission_id)
        mission.founder_approval_state = ApprovalStatus.PENDING
        mission.history.append(
            MissionHistoryEntry(
                from_status=mission.status,
                to_status=mission.status,
                action="controlled_revision_completed",
                note="One controlled Mission Zero revision completed for founder review.",
                metadata={
                    "original_score": comparison.original_overall_score,
                    "revised_score": comparison.revised_overall_score,
                },
            )
        )
        mission.updated_at = utc_now()
        self._runner.pilot.mission_manager.save_mission(mission)
        return self._runner.pilot.mission_manager.load_mission(mission_id)

    @staticmethod
    def _mission_summary(mission: Any) -> MissionSummary:
        return MissionSummary(
            mission_id=mission.mission_id,
            title=mission.title,
            current_state=mission.status,
            founder_approval=mission.founder_approval_state.value,
            assigned_employees=[
                item.employee_name for item in mission.assigned_employees
            ],
            artifact_count=len(mission.produced_artifacts),
            progress_percentage=mission.progress_percentage,
            artifacts=[
                ArtifactVersionSummary(
                    artifact_id=item.artifact_id,
                    artifact_type=item.artifact_type.value,
                    name=item.name,
                    version_number=item.version_number,
                    status=item.status.value,
                )
                for item in mission.produced_artifacts
            ],
        )
