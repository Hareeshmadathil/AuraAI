"""Composition runner for AuraAI's first founder-controlled content mission."""

from __future__ import annotations

from typing import Any

from core import OperationResult, ValidationError
from providers import PromptCategory, ProviderCapability, build_department_prompt
from providers.router import ProviderRouter
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventType

from company_missions.real_content_pilot import RealContentPilot, RealContentPilotInput
from company_missions.real_content_pilot.models import RealContentPilotResult
from company_missions.first_real_content.models import (
    EvidenceClassification,
    EvidenceItem,
    ArtifactVersionSummary,
    FirstContentMissionInput,
    FirstContentMissionResult,
    FounderReviewPackage,
    MetadataReviewPackage,
    MissionSummary,
    ProductionReviewPackage,
    ProviderUsageSummary,
    ProviderStageSummary,
    ShortFormReviewPackage,
    ThumbnailReviewPackage,
)


class FirstRealContentMissionRunner:
    """Adapt founder input into the existing pilot and review pipelines."""

    def __init__(
        self,
        *,
        provider_router: ProviderRouter | None = None,
        founder_approved_live_ai: bool = False,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.event_bus = event_bus or RuntimeEventBus()
        self._provider_router = provider_router
        self._founder_approved_live_ai = founder_approved_live_ai
        self.pilot = RealContentPilot(
            event_bus=self.event_bus,
        )

    def run(self, value: FirstContentMissionInput | dict[str, Any]) -> OperationResult:
        """Run deterministically to founder review; never render or publish."""

        try:
            result = self.run_typed(FirstContentMissionInput.model_validate(value))
        except Exception as error:
            return OperationResult.failure(
                "First content mission failed safely.",
                error_code=getattr(error, "error_code", "FIRST_CONTENT_MISSION_FAILED"),
            )
        return OperationResult.ok(
            "First content mission is ready for founder review.",
            data={"first_content_mission_result": result.model_dump(mode="json")},
        )

    def run_typed(self, value: FirstContentMissionInput) -> FirstContentMissionResult:
        """Return the typed review package for an already validated input."""

        try:
            return self._run_typed(value)
        except Exception:
            self._emit(RuntimeEventType.FIRST_CONTENT_MISSION_FAILED)
            raise

    def _run_typed(self, value: FirstContentMissionInput) -> FirstContentMissionResult:
        """Execute the validated mission while preserving typed failures."""

        live_authorized = bool(
            value.allow_live_gemini
            and self._founder_approved_live_ai
            and self._provider_router is not None
        )
        if value.allow_live_gemini and not live_authorized:
            if not value.allow_deterministic_fallback:
                raise ValidationError(
                    "Live AI requires explicit founder approval and injection.",
                    error_code="LIVE_AI_NOT_APPROVED",
                )
        if live_authorized:
            self.pilot = RealContentPilot(
                provider_router=self._provider_router,
                live_ai_approved=True,
                event_bus=self.event_bus,
            )
        self._emit(RuntimeEventType.FIRST_CONTENT_MISSION_STARTED)
        self._emit(RuntimeEventType.FOUNDER_INPUT_VALIDATED)
        self._emit(
            RuntimeEventType.LIVE_AI_AUTHORIZED
            if live_authorized
            else RuntimeEventType.LIVE_AI_DISABLED
        )
        operation = self.pilot.run(self._pilot_input(value))
        if not operation.success:
            raise ValidationError(
                operation.message,
                error_code=operation.error_code or "REAL_CONTENT_PILOT_FAILED",
            )
        pilot = self.pilot.last_result
        if pilot is None:
            pilot = RealContentPilotResult.model_validate(
                operation.data["real_content_pilot_result"]
            )
        advisories = (
            self._run_additive_live_advisories(value) if live_authorized else {}
        )
        if pilot.production_package is None or pilot.creative_quality_package is None:
            raise ValidationError(
                "Pilot did not expose its review packages.",
                error_code="MISSING_REVIEW_PACKAGE",
            )
        self._emit(RuntimeEventType.RESEARCH_COMPLETED)
        self._emit(RuntimeEventType.SEO_COMPLETED)
        self._emit(RuntimeEventType.SCRIPT_COMPLETED)
        if len(pilot.script_versions) > 1:
            self._emit(RuntimeEventType.SCRIPT_REVISED)
        self._emit(RuntimeEventType.QUALITY_REVIEW_COMPLETED)
        result = self._build_result(value, pilot, advisories)
        self._emit(RuntimeEventType.REVIEW_PACKAGE_CREATED)
        self._emit(RuntimeEventType.FOUNDER_CONTENT_REVIEW_REQUIRED)
        return result

    @staticmethod
    def _pilot_input(value: FirstContentMissionInput) -> RealContentPilotInput:
        notes = [
            *value.source_notes,
            *[f"Reference (verification required): {item}" for item in value.source_references],
            f"Preferred CTA: {value.primary_call_to_action}",
        ]
        return RealContentPilotInput(
            title=value.mission_title,
            objective=value.objective,
            topic=value.topic,
            target_audience=value.target_audience,
            audience_problem=value.audience_problem,
            audience_promise=value.audience_promise,
            primary_platform=value.primary_platform,
            language=value.language,
            tone=value.tone,
            target_duration_seconds=value.target_duration_seconds,
            content_goal=value.content_goal,
            preferred_call_to_action=value.primary_call_to_action,
            preferred_style=value.preferred_video_style,
            source_notes=notes,
            constraints=[
                *value.constraints,
                *(
                    ["Do not make any founder-prohibited claims."]
                    if value.prohibited_claims
                    else []
                ),
            ],
            primary_keyword=(value.preferred_keywords[0] if value.preferred_keywords else None),
            secondary_keywords=value.preferred_keywords[1:],
            founder_requires_live_ai=value.allow_live_gemini,
            allow_deterministic_fallback=value.allow_deterministic_fallback,
            sample_data=value.sample_data,
            requested_at=value.requested_at,
        )

    def _build_result(
        self,
        value: FirstContentMissionInput,
        pilot: RealContentPilotResult,
        advisories: dict[ProviderCapability, object],
    ) -> FirstContentMissionResult:
        production = pilot.production_package
        quality = pilot.creative_quality_package
        assert production is not None and quality is not None
        concept = next(
            item
            for item in production.thumbnail_plan.concepts
            if item.concept_id == production.thumbnail_plan.recommended_concept_id
        )
        usage = self._provider_usage(pilot)
        quality_blockers = [
            item.description for item in quality.gate.blocking_issues
        ]
        if quality.scores.overall < value.founder_quality_threshold:
            quality_blockers.append(
                "Creative Quality score is below the founder-defined threshold."
            )
        hook_advisory = advisories.get(ProviderCapability.HOOK)
        review_advisory = advisories.get(ProviderCapability.REVIEW)
        metadata_advisory = advisories.get(ProviderCapability.METADATA)
        return FirstContentMissionResult(
            mission_summary=MissionSummary(
                mission_id=pilot.mission.mission_id,
                title=pilot.mission.title,
                current_state=pilot.mission.status,
                founder_approval=pilot.mission.founder_approval_state.value,
                assigned_employees=[item.employee_name for item in pilot.mission.assigned_employees],
                artifact_count=len(pilot.mission.produced_artifacts),
                progress_percentage=pilot.mission.progress_percentage,
                artifacts=[
                    ArtifactVersionSummary(
                        artifact_id=item.artifact_id,
                        artifact_type=item.artifact_type.value,
                        name=item.name,
                        version_number=item.version_number,
                        status=item.status.value,
                    )
                    for item in pilot.mission.produced_artifacts
                ],
            ),
            mission=pilot.mission,
            pilot=pilot,
            production_package=production,
            creative_quality_package=quality,
            script_versions=pilot.script_versions or [pilot.script_artifact],
            founder_review=FounderReviewPackage(
                mission_objective=value.objective,
                target_audience=value.target_audience,
                research_summary=pilot.research_artifact.executive_summary,
                evidence_limitations=[
                    *pilot.research_artifact.verification_required,
                    "No live trend, search-volume, or competition research is claimed.",
                ],
                primary_keyword=pilot.seo_artifact.primary_keyword,
                title_options=pilot.seo_artifact.title_options,
                recommended_title=production.script.title,
                script_hook=production.script.hook,
                section_list=[section.title for section in production.script.sections],
                word_count=production.script.word_count,
                estimated_duration_seconds=production.script.total_estimated_duration_seconds,
                verification_warnings=pilot.script_artifact.claims_requiring_verification,
                quality_score=quality.scores.overall,
                gate_status=quality.gate.status.value,
                quality_breakdown_path="quality/quality-breakdown.md",
                revision_history=[f"Script v{item.version_number}" for item in pilot.script_versions],
                blocking_issues=quality_blockers,
                founder_decisions_required=["Approve, reject, or request one content revision."],
                provider_review_recommendations=list(
                    getattr(review_advisory, "findings", [])
                ),
            ),
            thumbnail_review=ThumbnailReviewPackage(
                headline=concept.primary_text,
                visual_direction=concept.visual_composition,
                review_notes=[production.thumbnail_plan.testing_hypothesis],
            ),
            short_form_review=ShortFormReviewPackage(
                clip_count=len(production.short_form_package.assets),
                hooks=[
                    *[item.hook for item in production.short_form_package.assets],
                    *list(getattr(hook_advisory, "alternatives", [])),
                ],
            ),
            metadata_review=MetadataReviewPackage(
                title=getattr(metadata_advisory, "title", production.script.title),
                description_guidance=getattr(
                    metadata_advisory, "description", value.content_goal
                ),
                keywords=[pilot.seo_artifact.primary_keyword, *pilot.seo_artifact.secondary_keywords],
                tags=list(getattr(metadata_advisory, "tags", pilot.seo_artifact.tags)),
                hashtags=pilot.seo_artifact.hashtags,
                cross_platform_captions={
                    item.platform: item.caption
                    for item in production.short_form_package.assets
                },
                evidence_classification=(
                    EvidenceClassification.VERIFICATION_REQUIRED
                    if value.source_references or pilot.script_artifact.claims_requiring_verification
                    else EvidenceClassification.DETERMINISTIC_ASSUMPTION
                ),
            ),
            production_review=ProductionReviewPackage(
                package_id=production.package_id,
                script_versions=max(1, len(pilot.script_versions)),
                quality_score=quality.scores.overall,
                blocking_issues=quality_blockers,
            ),
            provider_usage=ProviderUsageSummary(
                live_enabled=(value.allow_live_gemini and self.pilot.live_ai_approved),
                total_requests=sum(item.request_count for item in usage),
                fallback_used=any(item.fallback_used for item in usage),
                stages=usage,
            ),
            evidence_register=self._evidence_register(value, pilot),
        )

    def _run_additive_live_advisories(
        self, value: FirstContentMissionInput
    ) -> dict[ProviderCapability, object]:
        """Request bounded provider advice without replacing authoritative artifacts."""

        if self._provider_router is None:
            return {}
        outputs: dict[ProviderCapability, object] = {}
        for capability, category in (
            (ProviderCapability.HOOK, PromptCategory.CREATION),
            (ProviderCapability.REVIEW, PromptCategory.REVIEW),
            (ProviderCapability.METADATA, PromptCategory.STRATEGY),
        ):
            result = self._provider_router.route(
                capability,
                build_department_prompt(
                    f"first_content_{capability.value}_advisory",
                    category,
                    value.topic,
                ),
            )
            outputs[capability] = result.output
        return outputs

    def _provider_usage(
        self, pilot: RealContentPilotResult
    ) -> list[ProviderStageSummary]:
        if self._provider_router is not None and self.pilot.live_ai_approved:
            return [
                ProviderStageSummary(
                    capability=item.capability,
                    provider=item.provider,
                    fallback_used=item.fallback_used,
                    request_count=1,
                )
                for item in self._provider_router.build_state().usage
            ]
        capabilities = (
            ProviderCapability.RESEARCH,
            ProviderCapability.SEO,
            ProviderCapability.SCRIPT,
        )
        return [
            ProviderStageSummary(
                capability=capability,
                provider=item.provider,
                fallback_used=item.fallback_used,
                request_count=item.request_count,
            )
            for capability, item in zip(
                capabilities, pilot.provider_usage_summary, strict=True
            )
        ]

    @staticmethod
    def _evidence_register(
        value: FirstContentMissionInput,
        pilot: RealContentPilotResult,
    ) -> list[EvidenceItem]:
        items = [
            *[
                EvidenceItem(
                    classification=EvidenceClassification.FOUNDER_SUPPLIED_FACT,
                    summary=note,
                    verification_required=True,
                )
                for note in value.source_notes
            ],
            *[
                EvidenceItem(
                    classification=EvidenceClassification.FOUNDER_SUPPLIED_SOURCE,
                    summary=reference,
                    verification_required=True,
                )
                for reference in value.source_references
            ],
        ]
        if pilot.research_artifact.provider_used != "deterministic_local":
            items.append(
                EvidenceItem(
                    classification=EvidenceClassification.PROVIDER_SYNTHESIS,
                    summary="Provider advisory informed the research synthesis.",
                    verification_required=True,
                )
            )
        items.append(
            EvidenceItem(
                classification=EvidenceClassification.DETERMINISTIC_ASSUMPTION,
                summary="Local heuristic guidance is not independent evidence.",
                verification_required=True,
            )
        )
        return items

    def _emit(self, event_type: RuntimeEventType) -> None:
        self.event_bus.emit(event_type, event_type.value.replace("_", " ").title() + ".")
