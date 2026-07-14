"""Founder-controlled, resumable Real Content Pilot orchestration."""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from agents.directors import ResearchDirector
from agents.executive import AuraCEO, AuraCOO
from agents.specialists import SEOSpecialist
from agents.specialists.seo_specialist import SEOKeywordCandidate, SEOPlan
from company_missions.content_production import create_content_production_pipeline
from core import (
    ApprovalStatus,
    DepartmentName,
    MissionObjective,
    MissionRecord,
    MissionStatus,
    OperationResult,
    TaskRecord,
    ValidationError,
    utc_now,
)
from creative_quality.models import (
    CreativeQualityPipelineResult,
    QualityGateStatus,
)
from creative_quality.pipeline import create_creative_quality_pipeline
from mission_engine import (
    ArtifactRegistry,
    InMemoryMissionRepository,
    Mission,
    MissionArtifactType,
    MissionCapability,
    MissionExecutionStatus,
    MissionHistoryEntry,
    MissionManager,
)
from production.models import ProductionInput, ProductionPipelineResult
from providers import PromptCategory, ProviderCapability, build_department_prompt
from providers.router import ProviderRouter
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventSeverity, RuntimeEventType
from runtime_engine.state_manager import RuntimeStateManager

from company_missions.real_content_pilot.artifacts import (
    CreativeQualityArtifact,
    FounderReviewArtifact,
    FounderReviewStatus,
    ResearchArtifact,
    SEOArtifact,
    ScriptArtifact,
)
from company_missions.real_content_pilot.inputs import RealContentPilotInput
from company_missions.real_content_pilot.models import (
    PilotStageStatus,
    ProviderStageUsage,
    RealContentPilotResult,
    stage_result,
)


class TypedPilotArtifactStore:
    """Injected in-memory store that preserves immutable artifact versions."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Any] = {}

    def register(self, artifact: Any) -> None:
        """Register one typed artifact without overwrite."""

        key = str(artifact.artifact_id)
        if key in self._artifacts:
            raise ValidationError(
                "Typed pilot artifact already exists.",
                error_code="DUPLICATE_PILOT_ARTIFACT",
            )
        self._artifacts[key] = artifact

    def list_all(self) -> tuple[Any, ...]:
        """Return stored immutable artifacts in insertion order."""

        return tuple(self._artifacts.values())


class FounderReviewService:
    """Apply explicit founder decisions without implying publish approval."""

    def __init__(
        self,
        mission_manager: MissionManager,
        event_bus: RuntimeEventBus,
    ) -> None:
        self._manager = mission_manager
        self._events = event_bus

    def approve(
        self,
        result: RealContentPilotResult,
        *,
        notes: str,
    ) -> RealContentPilotResult:
        """Approve a safe review package and complete its mission."""

        if result.quality_artifact.blocking_issues or (
            result.quality_artifact.gate_status == QualityGateStatus.BLOCKED
        ):
            raise ValidationError(
                "Creative Quality blockers prevent founder approval.",
                error_code="QUALITY_BLOCKERS_PREVENT_APPROVAL",
            )
        self._manager.approve_founder_review(
            result.mission.mission_id,
            notes=notes,
        )
        mission = self._manager.update_mission_state(
            result.mission.mission_id,
            MissionExecutionStatus.COMPLETED,
            note="Founder approved content mission completion only.",
        )
        review = result.founder_review_artifact.model_copy(
            update={
                "review_status": FounderReviewStatus.APPROVED,
                "founder_notes": notes.strip(),
                "reviewed_at": utc_now(),
                "recommended_action": (
                    "Mission complete; rendering and publishing remain separate."
                ),
            }
        )
        self._emit(RuntimeEventType.FOUNDER_REVIEW_APPROVED, mission)
        self._emit(RuntimeEventType.REAL_MISSION_COMPLETED, mission)
        return result.model_copy(
            update={
                "mission": mission,
                "founder_review_artifact": review,
                "completed_at": utc_now(),
            }
        )

    def reject(
        self,
        result: RealContentPilotResult,
        *,
        reason: str,
    ) -> RealContentPilotResult:
        """Reject review while retaining all artifacts and history."""

        clean_reason = reason.strip()
        if not clean_reason:
            raise ValidationError("Founder rejection reason is required.")
        mission = self._manager.load_mission(result.mission.mission_id)
        mission.founder_approval_state = ApprovalStatus.REJECTED
        mission.history.append(
            MissionHistoryEntry(
                from_status=mission.status,
                to_status=mission.status,
                action="founder_rejected",
                note=clean_reason,
            )
        )
        self._manager.save_mission(mission)
        mission = self._manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.FAILED,
            note="Founder rejected the review package.",
            failure_reason=clean_reason,
        )
        review = result.founder_review_artifact.model_copy(
            update={
                "review_status": FounderReviewStatus.REJECTED,
                "founder_notes": clean_reason,
                "reviewed_at": utc_now(),
                "recommended_action": "Revise only after a new founder instruction.",
            }
        )
        self._emit(RuntimeEventType.FOUNDER_REVIEW_REJECTED, mission)
        return result.model_copy(
            update={"mission": mission, "founder_review_artifact": review}
        )

    def request_revision(
        self,
        result: RealContentPilotResult,
        *,
        notes: str,
    ) -> RealContentPilotResult:
        """Record one bounded revision request without changing state."""

        clean_notes = notes.strip()
        if not clean_notes:
            raise ValidationError("Founder revision notes are required.")
        if result.quality_artifact.revision_count >= 1:
            raise ValidationError(
                "The pilot revision limit has been reached.",
                error_code="PILOT_REVISION_LIMIT_REACHED",
            )
        if (
            result.founder_review_artifact.review_status
            == FounderReviewStatus.REVISION_REQUESTED
        ):
            raise ValidationError(
                "A founder revision has already been requested.",
                error_code="PILOT_REVISION_LIMIT_REACHED",
            )
        mission = self._manager.load_mission(result.mission.mission_id)
        mission.history.append(
            MissionHistoryEntry(
                from_status=mission.status,
                to_status=mission.status,
                action="founder_revision_requested",
                note=clean_notes,
            )
        )
        self._manager.save_mission(mission)
        review = result.founder_review_artifact.model_copy(
            update={
                "review_status": FounderReviewStatus.REVISION_REQUESTED,
                "founder_notes": clean_notes,
                "reviewed_at": utc_now(),
                "recommended_action": "Apply one bounded revision and re-review.",
            }
        )
        self._emit(RuntimeEventType.FOUNDER_REVISION_REQUESTED, mission)
        return result.model_copy(
            update={"mission": mission, "founder_review_artifact": review}
        )

    def _emit(self, event_type: RuntimeEventType, mission: Mission) -> None:
        self._events.emit(
            event_type,
            event_type.value.replace("_", " ").title() + ".",
            mission_id=mission.mission_id,
            department=DepartmentName.EXECUTIVE,
        )


class RealContentPilot:
    """Connect existing systems into one deterministic founder-gated flow."""

    def __init__(
        self,
        *,
        mission_manager: MissionManager | None = None,
        artifact_store: TypedPilotArtifactStore | None = None,
        provider_router: ProviderRouter | None = None,
        live_ai_approved: bool = False,
        event_bus: RuntimeEventBus | None = None,
        state_manager: RuntimeStateManager | None = None,
    ) -> None:
        self.event_bus = event_bus or RuntimeEventBus()
        self.state_manager = state_manager or RuntimeStateManager(self.event_bus)
        self.mission_manager = mission_manager or MissionManager(
            InMemoryMissionRepository(), ArtifactRegistry(), audit_actions=True
        )
        self.artifact_store = artifact_store or TypedPilotArtifactStore()
        self.provider_router = provider_router
        self.live_ai_approved = live_ai_approved
        self.research_director = ResearchDirector()
        self.seo_specialist = SEOSpecialist()
        self.production_pipeline, _ = create_content_production_pipeline(
            state_manager=self.state_manager,
            event_bus=self.event_bus,
        )
        self.quality_pipeline = create_creative_quality_pipeline(
            state_manager=self.state_manager,
            event_bus=self.event_bus,
        )
        self.executives = (AuraCEO(), AuraCOO())
        if provider_router is not None:
            self.research_director.configure_provider_router(provider_router)
            self.production_pipeline.script_writer.configure_provider_router(
                provider_router
            )
        self.founder_review = FounderReviewService(
            self.mission_manager, self.event_bus
        )
        self.last_result: RealContentPilotResult | None = None

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        """Return every existing employee involved in the pilot."""

        return (
            *self.executives,
            self.research_director,
            self.seo_specialist,
            *self.production_pipeline.employees,
            *self.quality_pipeline.employees,
        )

    def run(self, value: RealContentPilotInput | dict[str, Any]) -> OperationResult:
        """Run the pilot to FOUNDER_REVIEW without live calls by default."""

        pilot_input = RealContentPilotInput.model_validate(value)
        if pilot_input.founder_requires_live_ai and not (
            self.provider_router is not None and self.live_ai_approved
        ) and not pilot_input.allow_deterministic_fallback:
            return OperationResult.failure(
                "Live AI was requested but not explicitly approved/configured.",
                error_code="LIVE_AI_NOT_APPROVED",
            )
        mission = self.mission_manager.create_mission(
            title=pilot_input.title,
            objective=pilot_input.objective,
            capability=MissionCapability.CONTENT_PIPELINE,
        )
        self._emit(RuntimeEventType.REAL_MISSION_CREATED, mission)
        partial: dict[str, Any] = {}
        stages = []
        usage: list[ProviderStageUsage] = []
        try:
            mission = self._plan(mission)
            stages.append(
                stage_result(
                    MissionExecutionStatus.PLANNING,
                    PilotStageStatus.COMPLETED,
                    [employee.name for employee in self.employees],
                )
            )
            research, research_usage = self._research(mission, pilot_input)
            partial["research_artifact"] = research.model_dump(mode="json")
            usage.append(research_usage)
            stages.append(
                stage_result(
                    MissionExecutionStatus.RESEARCH,
                    PilotStageStatus.COMPLETED,
                    [self.research_director.name],
                    artifact_id=str(research.artifact_id),
                )
            )
            seo, seo_usage = self._seo(mission, pilot_input)
            partial["seo_artifact"] = seo.model_dump(mode="json")
            usage.append(seo_usage)
            stages.append(
                stage_result(
                    MissionExecutionStatus.SEO,
                    PilotStageStatus.COMPLETED,
                    [self.seo_specialist.name],
                    artifact_id=str(seo.artifact_id),
                )
            )
            script, package, script_usage = self._script(
                mission, pilot_input, research, seo
            )
            partial["script_artifact"] = script.model_dump(mode="json")
            usage.append(script_usage)
            stages.append(
                stage_result(
                    MissionExecutionStatus.SCRIPT,
                    PilotStageStatus.COMPLETED,
                    [self.production_pipeline.script_writer.name],
                    artifact_id=str(script.artifact_id),
                )
            )
            quality, quality_package, revised_package, revised_script = self._quality(
                mission, package, script
            )
            partial["quality_artifact"] = quality.model_dump(mode="json")
            stages.append(
                stage_result(
                    MissionExecutionStatus.SCRIPT,
                    PilotStageStatus.COMPLETED,
                    [employee.name for employee in self.quality_pipeline.employees],
                    artifact_id=str(quality.artifact_id),
                )
            )
            review = self._prepare_founder_review(
                mission, research, seo, script, quality
            )
            mission = self.mission_manager.load_mission(mission.mission_id)
            stages.append(
                stage_result(
                    MissionExecutionStatus.FOUNDER_REVIEW,
                    PilotStageStatus.AWAITING_FOUNDER,
                    [self.executives[0].name],
                    artifact_id=str(review.artifact_id),
                )
            )
            result = RealContentPilotResult(
                mission=mission,
                research_artifact=research,
                seo_artifact=seo,
                script_artifact=script,
                quality_artifact=quality,
                founder_review_artifact=review,
                stage_results=stages,
                runtime_snapshot=self._safe_runtime_snapshot(mission),
                provider_usage_summary=usage,
                production_package=revised_package or package,
                creative_quality_package=quality_package,
                script_versions=[script, *([revised_script] if revised_script else [])],
            )
            self.last_result = result
            return OperationResult.ok(
                "Real Content Pilot is ready for founder review.",
                data={"real_content_pilot_result": result.model_dump(mode="json")},
            )
        except Exception as error:
            self._fail_safely(mission, error)
            return OperationResult.failure(
                "Real Content Pilot failed safely; completed artifacts were retained.",
                error_code=getattr(error, "error_code", "REAL_CONTENT_PILOT_FAILED"),
                data={
                    "exception_type": error.__class__.__name__,
                    "partial_artifacts": partial,
                    "stage_results": [item.model_dump(mode="json") for item in stages],
                },
            )

    def _plan(self, mission: Mission) -> Mission:
        unique: dict[str, BaseEmployee] = {
            employee.job_title: employee for employee in self.employees
        }
        for employee in unique.values():
            self.mission_manager.assign_employee(
                mission.mission_id,
                employee_id=employee.agent_id,
                employee_name=employee.name,
                department=employee.department,
            )
        mission = self.mission_manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.PLANNING,
            note=(
                "Research, SEO, script, quality, and founder-review stages planned; "
                "deterministic fallback retained."
            ),
        )
        self._emit(RuntimeEventType.REAL_MISSION_PLANNED, mission)
        return mission

    def _research(
        self, mission: Mission, value: RealContentPilotInput
    ) -> tuple[ResearchArtifact, ProviderStageUsage]:
        self._emit(RuntimeEventType.RESEARCH_STAGE_STARTED, mission)
        legacy = MissionRecord(
            mission_id=mission.mission_id,
            title=mission.title,
            description=mission.objective,
            status=MissionStatus.APPROVED,
            approval_status=ApprovalStatus.APPROVED,
            objectives=[
                MissionObjective(
                    description=mission.objective,
                    success_metric="Typed founder-review package created",
                )
            ],
        )
        result = self._execute(
            self.research_director,
            TaskRecord(
                title="Plan evidence-aware pilot research",
                department=DepartmentName.RESEARCH,
                input_data={"mission": legacy},
            ),
        )
        advisory = result.data.get("provider_advisory")
        provider, fallback, requests = self._provider_metadata(advisory)
        findings = (
            advisory.get("output", {}).get("findings", [])
            if advisory
            else []
        )
        artifact = ResearchArtifact(
            mission_id=mission.mission_id,
            topic=value.topic,
            executive_summary=(
                f"Research frames {value.topic} for {value.target_audience} "
                "using supplied evidence and explicit verification limits."
            ),
            audience_needs=[value.audience_problem, value.audience_promise],
            key_questions=[
                f"What does the audience need to understand about {value.topic}?",
                "Which material claims require independent verification?",
            ],
            evidence_summary=[*value.source_notes, *findings],
            supplied_sources=list(value.source_notes),
            verification_required=[
                "Verify every material or time-sensitive claim before publication."
            ],
            limitations=[
                "No external web search was performed.",
                "Provider synthesis is not independent evidence.",
            ],
            provider_used=provider,
            fallback_used=fallback,
        )
        self._register_typed(
            mission, artifact, MissionArtifactType.RESEARCH, self.research_director
        )
        self.mission_manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.RESEARCH,
            note="Research artifact registered before stage advancement.",
        )
        self._emit(RuntimeEventType.RESEARCH_ARTIFACT_CREATED, mission)
        return artifact, ProviderStageUsage(
            stage=MissionExecutionStatus.RESEARCH,
            provider=provider,
            fallback_used=fallback,
            request_count=requests,
        )

    def _seo(
        self, mission: Mission, value: RealContentPilotInput
    ) -> tuple[SEOArtifact, ProviderStageUsage]:
        self._emit(RuntimeEventType.SEO_STAGE_STARTED, mission)
        keywords = list(
            dict.fromkeys(
                [
                    value.primary_keyword or value.topic,
                    *value.secondary_keywords,
                    f"{value.topic} guide",
                    f"{value.topic} for beginners",
                ]
            )
        )
        candidates = [
            SEOKeywordCandidate(
                keyword=keyword,
                relevance_score=max(70, 95 - index * 4),
                search_intent_score=max(65, 90 - index * 3),
                competition_score=min(80, 35 + index * 8),
                monetization_score=max(55, 75 - index * 3),
                platform_fit_score=max(70, 92 - index * 4),
            )
            for index, keyword in enumerate(keywords)
        ]
        result = self._execute(
            self.seo_specialist,
            TaskRecord(
                title="Create deterministic pilot SEO plan",
                department=DepartmentName.MARKETING,
                input_data={
                    "topic": value.topic,
                    "target_audience": value.target_audience,
                    "platform": value.primary_platform,
                    "keyword_candidates": candidates,
                },
            ),
        )
        plan = SEOPlan.model_validate(result.data["seo_plan"])
        advisory = None
        if self.provider_router is not None:
            routed = self.provider_router.route(
                ProviderCapability.SEO,
                build_department_prompt(
                    "real_content_pilot_seo_advisory",
                    PromptCategory.STRATEGY,
                    value.topic,
                ),
            )
            advisory = routed.model_dump(mode="json")
        provider, fallback, requests = self._provider_metadata(advisory)
        advised_primary = (
            advisory.get("output", {}).get("primary_keyword")
            if advisory
            else None
        )
        primary = advised_primary or plan.recommended_primary_keyword
        artifact = SEOArtifact(
            mission_id=mission.mission_id,
            primary_keyword=primary,
            secondary_keywords=plan.secondary_keywords,
            search_intent="Educational problem-solving intent",
            title_options=[
                f"{primary}: A Practical Guide",
                f"How to Approach {primary} Responsibly",
            ],
            description_outline=[
                value.audience_problem,
                value.audience_promise,
                "Limitations and verification notes",
            ],
            tags=[primary, *plan.secondary_keywords],
            hashtags=plan.hashtag_guidance,
            chapter_keywords=[primary, *plan.secondary_keywords[:3]],
            difficulty_notes=[
                "Competition is a deterministic relative score, not live volume data."
            ],
            verification_required=[
                "Validate live search demand before publication."
            ],
            provider_used=provider,
            fallback_used=fallback,
        )
        self._register_typed(
            mission, artifact, MissionArtifactType.KEYWORDS, self.seo_specialist
        )
        self.mission_manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.SEO,
            note="SEO artifact registered before stage advancement.",
        )
        self._emit(RuntimeEventType.SEO_ARTIFACT_CREATED, mission)
        return artifact, ProviderStageUsage(
            stage=MissionExecutionStatus.SEO,
            provider=provider,
            fallback_used=fallback,
            request_count=requests,
        )

    def _script(
        self,
        mission: Mission,
        value: RealContentPilotInput,
        research: ResearchArtifact,
        seo: SEOArtifact,
    ) -> tuple[ScriptArtifact, Any, ProviderStageUsage]:
        self._emit(RuntimeEventType.SCRIPT_STAGE_STARTED, mission)
        before = len(
            self.provider_router.build_state().usage
            if self.provider_router is not None
            else []
        )
        operation = self.production_pipeline.run(
            ProductionInput(
                mission_id=mission.mission_id,
                brand_name="AuraAI",
                topic=value.topic,
                working_title=seo.title_options[0],
                target_audience=value.target_audience,
                audience_problem=value.audience_problem,
                audience_promise=value.audience_promise,
                content_pillars=["Evidence-aware education", "Practical action"],
                primary_platform=value.primary_platform,
                target_duration_seconds=value.target_duration_seconds,
                language=value.language,
                tone=value.tone,
                campaign_goal=value.content_goal,
                primary_keyword=seo.primary_keyword,
                secondary_keywords=seo.secondary_keywords,
                source_notes=[
                    *research.supplied_sources,
                    *research.verification_required,
                ],
                constraints=[
                    *value.constraints,
                    "Do not guarantee outcomes or fabricate statistics.",
                ],
                preferred_call_to_action=(
                    value.preferred_call_to_action
                    or "Apply one low-risk step, verify the evidence, and record results."
                ),
                preferred_style=value.preferred_style,
                requires_founder_approval=True,
                sample_data=value.sample_data,
            ),
            founder_approved=False,
        )
        if not operation.success:
            raise ValidationError(
                operation.message,
                error_code=operation.error_code or "PRODUCTION_STAGE_FAILED",
            )
        production = ProductionPipelineResult.model_validate(
            operation.data["production_pipeline_result"]
        ).package
        script = production.script
        usage_values = (
            self.provider_router.build_state().usage[before:]
            if self.provider_router is not None
            else []
        )
        relevant = [
            item for item in usage_values if item.capability == ProviderCapability.SCRIPT
        ]
        provider = relevant[-1].provider if relevant else "deterministic_local"
        fallback = relevant[-1].fallback_used if relevant else True
        artifact = ScriptArtifact(
            mission_id=mission.mission_id,
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
            source_notes=list(value.source_notes),
            provider_used=provider,
            fallback_used=fallback,
        )
        self._register_typed(
            mission,
            artifact,
            MissionArtifactType.SCRIPT,
            self.production_pipeline.script_writer,
        )
        self.mission_manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.SCRIPT,
            note="Script artifact registered before stage advancement.",
        )
        self._emit(RuntimeEventType.SCRIPT_ARTIFACT_CREATED, mission)
        return artifact, production, ProviderStageUsage(
            stage=MissionExecutionStatus.SCRIPT,
            provider=provider,
            fallback_used=fallback,
            request_count=min(1, len(relevant)),
        )

    def _quality(
        self, mission: Mission, package: Any, script: ScriptArtifact
    ) -> tuple[CreativeQualityArtifact, Any, Any | None, ScriptArtifact | None]:
        self._emit(RuntimeEventType.CREATIVE_QUALITY_STAGE_STARTED, mission)
        operation = self.quality_pipeline.run(package)
        data = operation.data.get("creative_quality_pipeline_result")
        if data is None:
            raise ValidationError(
                operation.message,
                error_code=operation.error_code or "CREATIVE_QUALITY_FAILED",
            )
        result = CreativeQualityPipelineResult.model_validate(data)
        quality = result.quality_package
        artifact = CreativeQualityArtifact(
            mission_id=mission.mission_id,
            quality_package_id=quality.package_id,
            overall_score=quality.scores.overall,
            gate_status=quality.gate.status,
            blocking_issues=[
                issue.description for issue in quality.gate.blocking_issues
            ],
            warnings=list(quality.gate.warnings),
            revision_count=quality.revision_plan.revision_count,
            founder_override_allowed=quality.gate.founder_override_allowed,
        )
        self._register_typed(
            mission,
            artifact,
            MissionArtifactType.QUALITY_REPORT,
            self.quality_pipeline.creative_director,
        )
        revised_artifact = None
        if result.revised_production_package is not None:
            revised = result.revised_production_package.script
            revised_artifact = ScriptArtifact(
                mission_id=mission.mission_id,
                version_number=2,
                parent_artifact_id=script.artifact_id,
                title=revised.title,
                hook=revised.hook,
                sections=[section.narration for section in revised.sections],
                call_to_action=revised.call_to_action,
                word_count=revised.word_count,
                estimated_duration_seconds=revised.total_estimated_duration_seconds,
                claims_requiring_verification=[
                    claim
                    for section in revised.sections
                    for claim in section.claims_requiring_verification
                ],
                source_notes=script.source_notes,
                provider_used=script.provider_used,
                fallback_used=script.fallback_used,
            )
            self._register_typed(
                mission,
                revised_artifact,
                MissionArtifactType.SCRIPT,
                self.production_pipeline.script_writer,
                parent_artifact_id=script.artifact_id,
            )
        self._emit(RuntimeEventType.CREATIVE_QUALITY_ARTIFACT_CREATED, mission)
        return (
            artifact,
            quality,
            result.revised_production_package,
            revised_artifact,
        )

    def _prepare_founder_review(
        self,
        mission: Mission,
        research: ResearchArtifact,
        seo: SEOArtifact,
        script: ScriptArtifact,
        quality: CreativeQualityArtifact,
    ) -> FounderReviewArtifact:
        review = FounderReviewArtifact(
            mission_id=mission.mission_id,
            research_summary=research.executive_summary,
            seo_summary=f"Primary keyword: {seo.primary_keyword}.",
            script_summary=(
                f"{script.title}; {len(script.sections)} sections; "
                f"{script.word_count} words."
            ),
            quality_summary=(
                f"Score {quality.overall_score}; gate {quality.gate_status.value}."
            ),
            blocking_items=quality.blocking_issues,
            recommended_action=(
                "Resolve blocking issues before approval."
                if quality.blocking_issues
                else "Founder may approve, reject, or request one revision."
            ),
        )
        self._register_typed(
            mission,
            review,
            MissionArtifactType.APPROVAL_NOTES,
            self.executives[0],
        )
        self.mission_manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.FOUNDER_REVIEW,
            note="Founder review package registered; no rendering or publishing approved.",
        )
        self._emit(RuntimeEventType.FOUNDER_REVIEW_READY, mission)
        return review

    def _register_typed(
        self,
        mission: Mission,
        artifact: Any,
        artifact_type: MissionArtifactType,
        producer: BaseEmployee,
        *,
        parent_artifact_id: Any = None,
    ) -> None:
        self.artifact_store.register(artifact)
        self.mission_manager.register_artifact(
            mission.mission_id,
            artifact_type=artifact_type,
            name=artifact.__class__.__name__,
            summary=self._artifact_summary(artifact),
            produced_by_employee_id=producer.agent_id,
            producer=producer.name,
            stage=self.mission_manager.load_mission(mission.mission_id).status,
            parent_artifact_id=parent_artifact_id,
            metadata_reference=f"memory://pilot/{artifact.artifact_id}",
            metadata={
                "typed_artifact_id": str(artifact.artifact_id),
                "typed_version": artifact.version_number,
            },
        )

    @staticmethod
    def _artifact_summary(artifact: Any) -> str:
        if isinstance(artifact, ResearchArtifact):
            return artifact.executive_summary
        if isinstance(artifact, SEOArtifact):
            return f"SEO plan centered on {artifact.primary_keyword}."
        if isinstance(artifact, ScriptArtifact):
            return f"{artifact.title}; {artifact.word_count} words."
        if isinstance(artifact, CreativeQualityArtifact):
            return f"Quality score {artifact.overall_score}; {artifact.gate_status.value}."
        return f"Founder review status: {artifact.review_status.value}."

    @staticmethod
    def _execute(employee: BaseEmployee, task: TaskRecord) -> OperationResult:
        employee.accept_task(task)
        result = employee.execute_current_task()
        if employee.current_task is not None and not employee.has_active_task:
            employee.clear_current_task()
        if not result.success:
            raise ValidationError(
                result.message,
                error_code=result.error_code or "EMPLOYEE_STAGE_FAILED",
            )
        return result

    @staticmethod
    def _provider_metadata(
        advisory: dict[str, Any] | None,
    ) -> tuple[str, bool, int]:
        if advisory is None:
            return "deterministic_local", True, 0
        return (
            str(advisory.get("provider", "deterministic")),
            bool(advisory.get("fallback_used", False)),
            1,
        )

    def _safe_runtime_snapshot(self, mission: Mission) -> dict[str, Any]:
        snapshot = self.state_manager.snapshot().model_dump(mode="json")
        snapshot["real_content_pilot"] = {
            "mission_id": str(mission.mission_id),
            "title": mission.title,
            "status": mission.status.value,
            "progress_percentage": mission.progress_percentage,
            "artifact_count": len(mission.produced_artifacts),
            "founder_approval_state": mission.founder_approval_state.value,
        }
        snapshot["pilot_events"] = [
            {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "mission_id": str(event.mission_id) if event.mission_id else None,
            }
            for event in self.event_bus.filter_by_mission(mission.mission_id)
        ]
        return snapshot

    def _fail_safely(self, mission: Mission, error: Exception) -> None:
        current = self.mission_manager.load_mission(mission.mission_id)
        if not current.is_terminal:
            self.mission_manager.update_mission_state(
                current.mission_id,
                MissionExecutionStatus.FAILED,
                failure_reason=error.__class__.__name__,
                note="Pilot failed safely; partial artifacts retained.",
            )
        self.event_bus.emit(
            RuntimeEventType.REAL_MISSION_FAILED,
            "Real mission failed safely; content was not published.",
            mission_id=mission.mission_id,
            severity=RuntimeEventSeverity.ERROR,
            metadata={"safe_error_code": getattr(error, "error_code", "PILOT_FAILED")},
        )

    def _emit(self, event_type: RuntimeEventType, mission: Mission) -> None:
        self.event_bus.emit(
            event_type,
            event_type.value.replace("_", " ").title() + ".",
            mission_id=mission.mission_id,
        )


def create_founder_controlled_live_pilot(
    value: RealContentPilotInput,
    provider_router: ProviderRouter,
    live_ai_approved: bool,
) -> RealContentPilot:
    """Compose, but do not execute, an explicitly approved live-capable pilot."""

    if not live_ai_approved:
        raise ValidationError(
            "Explicit founder live-AI approval is required.",
            error_code="LIVE_AI_NOT_APPROVED",
        )
    if not value.founder_requires_live_ai:
        raise ValidationError(
            "Pilot input must explicitly request live AI.",
            error_code="LIVE_AI_NOT_REQUESTED",
        )
    return RealContentPilot(
        provider_router=provider_router,
        live_ai_approved=True,
    )
