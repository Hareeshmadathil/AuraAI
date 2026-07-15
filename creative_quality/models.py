"""Typed models for AuraAI's deterministic Content Quality Engine."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from core import AuraBaseModel, TaskPriority, utc_now
from production.models import ProductionPackage


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware.")
    return value


def _aware_optional(value: datetime | None) -> datetime | None:
    return _aware(value) if value is not None else None


class CreativeQualityStage(StrEnum):
    """Ordered stages in the creative-quality workflow."""

    INTAKE = "intake"
    HOOK_REVIEW = "hook_review"
    STORY_REVIEW = "story_review"
    RETENTION_REVIEW = "retention_review"
    MOTION_REVIEW = "motion_review"
    SUBTITLE_REVIEW = "subtitle_review"
    THUMBNAIL_REVIEW = "thumbnail_review"
    FACTUALITY_REVIEW = "factuality_review"
    SCORING = "scoring"
    REVISION = "revision"
    APPROVAL = "approval"
    PASSED = "passed"
    FAILED = "failed"


class QualitySeverity(StrEnum):
    """Impact of a quality issue."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


class QualityDimension(StrEnum):
    """Dimensions measured by the internal quality heuristic."""

    HOOK = "hook"
    STORY = "story"
    PACING = "pacing"
    RETENTION = "retention"
    CLARITY = "clarity"
    MOTION = "motion"
    SUBTITLES = "subtitles"
    THUMBNAIL = "thumbnail"
    FACTUALITY = "factuality"
    TRUST = "trust"
    CALL_TO_ACTION = "call_to_action"
    PRODUCTION_COMPLETENESS = "production_completeness"


class QualityDepartment(StrEnum):
    """Founder-facing Creative Quality review departments."""

    HOOK = "hook"
    STORY = "story"
    RETENTION = "retention"
    MOTION = "motion"
    SUBTITLES = "subtitles"
    THUMBNAIL = "thumbnail"
    FACTUALITY = "factuality"


class QualityGateStatus(StrEnum):
    """Possible pre-render quality outcomes."""

    PASSED = "passed"
    REVISION_REQUIRED = "revision_required"
    FOUNDER_OVERRIDE_REQUIRED = "founder_override_required"
    BLOCKED = "blocked"


class HookAnalysis(AuraBaseModel):
    analysis_id: UUID = Field(default_factory=uuid4)
    original_hook: str = Field(min_length=1)
    hook_type: str = Field(min_length=1)
    clarity_score: float = Field(ge=0, le=100)
    curiosity_score: float = Field(ge=0, le=100)
    relevance_score: float = Field(ge=0, le=100)
    credibility_score: float = Field(ge=0, le=100)
    emotional_score: float = Field(ge=0, le=100)
    first_five_seconds_score: float = Field(ge=0, le=100)
    first_fifteen_seconds_score: float = Field(ge=0, le=100)
    open_loops: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    improved_hook: str = Field(min_length=1)
    claims_requiring_verification: list[str] = Field(default_factory=list)
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)


class StorySectionAnalysis(AuraBaseModel):
    section_id: UUID
    section_title: str = Field(min_length=1)
    narrative_role: str = Field(min_length=1)
    clarity_score: float = Field(ge=0, le=100)
    pacing_score: float = Field(ge=0, le=100)
    relevance_score: float = Field(ge=0, le=100)
    emotional_progression_score: float = Field(ge=0, le=100)
    transition_score: float = Field(ge=0, le=100)
    repetition_detected: bool = False
    weak_points: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


class StoryFlowReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    sections: list[StorySectionAnalysis] = Field(min_length=1)
    narrative_arc: str = Field(min_length=1)
    opening_strength: float = Field(ge=0, le=100)
    middle_strength: float = Field(ge=0, le=100)
    ending_strength: float = Field(ge=0, le=100)
    transition_quality: float = Field(ge=0, le=100)
    total_story_score: float = Field(ge=0, le=100)
    reordered_section_ids: list[UUID] | None = None
    recommendations: list[str] = Field(default_factory=list)
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)


class RetentionRisk(AuraBaseModel):
    risk_id: UUID = Field(default_factory=uuid4)
    timestamp_seconds: float = Field(ge=0)
    section_id: UUID | None = None
    severity: QualitySeverity
    risk_type: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    likely_viewer_response: str = Field(min_length=1)
    remediation: str = Field(min_length=1)


class RetentionReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    production_duration_seconds: float = Field(gt=0)
    estimated_average_retention_score: float = Field(ge=0, le=100)
    first_30_seconds_score: float = Field(ge=0, le=100)
    middle_retention_score: float = Field(ge=0, le=100)
    ending_retention_score: float = Field(ge=0, le=100)
    risks: list[RetentionRisk] = Field(default_factory=list)
    pattern_interrupt_recommendations: list[str] = Field(default_factory=list)
    curiosity_loop_recommendations: list[str] = Field(default_factory=list)
    engagement_prompts: list[str] = Field(default_factory=list)
    call_to_action_timing: float = Field(ge=0)
    heuristic_analysis: bool = True
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "RetentionReport":
        values = [risk.timestamp_seconds for risk in self.risks]
        values.append(self.call_to_action_timing)
        if any(value > self.production_duration_seconds for value in values):
            raise ValueError("Retention timestamps must fit production duration.")
        return self


class MotionCue(AuraBaseModel):
    cue_id: UUID = Field(default_factory=uuid4)
    scene_id: UUID
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    motion_type: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    intensity: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    accessibility_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timing(self) -> "MotionCue":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Motion cue end must be after its start.")
        return self


class MotionPlan(AuraBaseModel):
    plan_id: UUID = Field(default_factory=uuid4)
    storyboard_id: UUID
    cues: list[MotionCue] = Field(min_length=1)
    transition_strategy: str = Field(min_length=1)
    kinetic_typography_strategy: str = Field(min_length=1)
    infographic_strategy: str = Field(min_length=1)
    visual_rhythm_score: float = Field(ge=0, le=100)
    overload_risks: list[str] = Field(default_factory=list)
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)


class SubtitleLineAnalysis(AuraBaseModel):
    segment_index: int = Field(ge=1)
    original_text: str = Field(min_length=1)
    optimized_text: str = Field(min_length=1)
    characters_per_line: int = Field(ge=1, le=42)
    reading_speed_cps: float = Field(gt=0)
    line_count: int = Field(ge=1)
    keyword_highlights: list[str] = Field(default_factory=list)
    readability_score: float = Field(ge=0, le=100)
    safe_area_notes: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class SubtitleOptimization(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    subtitle_package_id: UUID
    lines: list[SubtitleLineAnalysis] = Field(min_length=1)
    mobile_readability_score: float = Field(ge=0, le=100)
    timing_score: float = Field(ge=0, le=100)
    emphasis_score: float = Field(ge=0, le=100)
    overall_subtitle_score: float = Field(ge=0, le=100)
    optimized_srt_text: str = Field(min_length=1)
    optimized_vtt_text: str = Field(min_length=1)
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)

    @model_validator(mode="after")
    def validate_vtt(self) -> "SubtitleOptimization":
        if not self.optimized_vtt_text.startswith("WEBVTT"):
            raise ValueError("Optimized WebVTT must start with WEBVTT.")
        return self


class ThumbnailConceptScore(AuraBaseModel):
    concept_id: UUID
    clarity_score: float = Field(ge=0, le=100)
    curiosity_score: float = Field(ge=0, le=100)
    contrast_score: float = Field(ge=0, le=100)
    emotional_score: float = Field(ge=0, le=100)
    trust_score: float = Field(ge=0, le=100)
    mobile_readability_score: float = Field(ge=0, le=100)
    topic_alignment_score: float = Field(ge=0, le=100)
    clickbait_risk: float = Field(ge=0, le=100)
    total_score: float = Field(ge=0, le=100)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ThumbnailQualityReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    thumbnail_plan_id: UUID
    concepts: list[ThumbnailConceptScore] = Field(min_length=1)
    recommended_concept_id: UUID
    recommendation_reason: str = Field(min_length=1)
    ab_test_hypothesis: str = Field(min_length=1)
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)

    @model_validator(mode="after")
    def validate_recommendation(self) -> "ThumbnailQualityReport":
        if self.recommended_concept_id not in {
            concept.concept_id for concept in self.concepts
        }:
            raise ValueError("Recommended thumbnail concept must be scored.")
        return self


class FactualClaimReview(AuraBaseModel):
    claim_id: UUID = Field(default_factory=uuid4)
    claim_text: str = Field(min_length=1)
    section_id: UUID | None = None
    verification_required: bool
    evidence_supplied: bool
    risk_level: QualitySeverity
    issue: str = Field(min_length=1)
    remediation: str = Field(min_length=1)
    source_notes: list[str] = Field(default_factory=list)


class FactualityReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    claims: list[FactualClaimReview] = Field(default_factory=list)
    unsupported_claim_count: int = Field(ge=0)
    high_risk_claim_count: int = Field(ge=0)
    disclaimer_requirements: list[str] = Field(default_factory=list)
    prohibited_claims_found: list[str] = Field(default_factory=list)
    factuality_score: float = Field(ge=0, le=100)
    passed: bool
    reviewed_at: datetime = Field(default_factory=utc_now)

    _aware_reviewed_at = field_validator("reviewed_at")(_aware)


class CreativeQualityIssue(AuraBaseModel):
    issue_id: UUID = Field(default_factory=uuid4)
    dimension: QualityDimension
    severity: QualitySeverity
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    affected_reference: str = Field(min_length=1)
    remediation: str | None = None
    blocking: bool = False

    @model_validator(mode="after")
    def validate_blocker(self) -> "CreativeQualityIssue":
        if self.blocking and not (self.remediation and self.remediation.strip()):
            raise ValueError("Every blocking issue requires remediation.")
        if self.severity == QualitySeverity.BLOCKING and not self.blocking:
            raise ValueError("Blocking severity must set blocking=True.")
        return self


class CreativeQualityScores(AuraBaseModel):
    hook: float = Field(ge=0, le=100)
    story: float = Field(ge=0, le=100)
    pacing: float = Field(ge=0, le=100)
    retention: float = Field(ge=0, le=100)
    clarity: float = Field(ge=0, le=100)
    motion: float = Field(ge=0, le=100)
    subtitles: float = Field(ge=0, le=100)
    thumbnail: float = Field(ge=0, le=100)
    factuality: float = Field(ge=0, le=100)
    trust: float = Field(ge=0, le=100)
    call_to_action: float = Field(ge=0, le=100)
    production_completeness: float = Field(ge=0, le=100)
    overall: float = Field(ge=0, le=100)


class CreativeQualityGate(AuraBaseModel):
    gate_id: UUID = Field(default_factory=uuid4)
    status: QualityGateStatus
    minimum_required_score: float = Field(ge=0, le=100)
    actual_score: float = Field(ge=0, le=100)
    blocking_issues: list[CreativeQualityIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    founder_override_allowed: bool = False
    founder_override_used: bool = False
    rationale: str = Field(min_length=1)
    evaluated_at: datetime = Field(default_factory=utc_now)

    _aware_evaluated_at = field_validator("evaluated_at")(_aware)

    @model_validator(mode="after")
    def validate_gate(self) -> "CreativeQualityGate":
        if self.status == QualityGateStatus.PASSED and self.blocking_issues:
            raise ValueError("Quality gate cannot pass with blocking issues.")
        unsafe = any(
            issue.dimension in {QualityDimension.FACTUALITY, QualityDimension.TRUST}
            and issue.severity in {QualitySeverity.HIGH, QualitySeverity.BLOCKING}
            for issue in self.blocking_issues
        )
        if unsafe and (self.founder_override_allowed or self.founder_override_used):
            raise ValueError(
                "Unsafe factuality or trust blockers cannot be overridden."
            )
        if self.founder_override_used and not self.founder_override_allowed:
            raise ValueError("Founder override use must be explicitly allowed.")
        return self


class RevisionAction(AuraBaseModel):
    action_id: UUID = Field(default_factory=uuid4)
    priority: TaskPriority
    dimension: QualityDimension
    target_reference: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    expected_improvement: str = Field(min_length=1)
    requires_human_review: bool = False
    completed: bool = False


class RevisionPlan(AuraBaseModel):
    plan_id: UUID = Field(default_factory=uuid4)
    actions: list[RevisionAction] = Field(default_factory=list)
    estimated_quality_gain: float = Field(ge=0, le=100)
    mandatory_actions: list[UUID] = Field(default_factory=list)
    optional_actions: list[UUID] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    _aware_created_at = field_validator("created_at")(_aware)


class QualityDepartmentBreakdown(AuraBaseModel):
    """Explain one founder-facing department's quality contribution."""

    department: QualityDepartment
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    passed: bool
    contributing_dimensions: list[QualityDimension] = Field(min_length=1)
    blockers: list[CreativeQualityIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    suggested_employee: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pass_status(self) -> "QualityDepartmentBreakdown":
        if self.passed and self.blockers:
            raise ValueError("A department with blockers cannot pass.")
        return self


class QualityRecommendation(AuraBaseModel):
    """Actionable recommendation with explicit employee ownership."""

    department: QualityDepartment
    recommendation: str = Field(min_length=1)
    suggested_employee: str = Field(min_length=1)
    priority: QualitySeverity


class QualityBreakdown(AuraBaseModel):
    """Founder-ready explanation derived from the unchanged quality score."""

    executive_summary: str = Field(min_length=1)
    overall_score: float = Field(ge=0, le=100)
    gate_status: QualityGateStatus
    departments: list[QualityDepartmentBreakdown] = Field(
        min_length=7,
        max_length=7,
    )
    blocking_issues: list[CreativeQualityIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[QualityRecommendation] = Field(default_factory=list)
    estimated_improvement_points: float = Field(ge=0, le=100)
    estimated_score_after_revision: float = Field(ge=0, le=100)
    heuristic_notice: str = (
        "Explanatory projection of the existing deterministic quality score; "
        "estimated improvement is not a performance guarantee."
    )

    @model_validator(mode="after")
    def validate_breakdown(self) -> "QualityBreakdown":
        departments = [item.department for item in self.departments]
        if len(set(departments)) != len(departments):
            raise ValueError("Quality departments must be unique.")
        if set(departments) != set(QualityDepartment):
            raise ValueError("Every quality department must be reported.")
        if any(not issue.blocking for issue in self.blocking_issues):
            raise ValueError("Breakdown blockers must be blocking issues.")
        severity_order = {
            QualitySeverity.BLOCKING: 4,
            QualitySeverity.HIGH: 3,
            QualitySeverity.MEDIUM: 2,
            QualitySeverity.LOW: 1,
            QualitySeverity.INFO: 0,
        }
        priorities = [severity_order[item.severity] for item in self.blocking_issues]
        if priorities != sorted(priorities, reverse=True):
            raise ValueError("Blocking issues must be sorted by severity.")
        return self


class CreativeQualityPackage(AuraBaseModel):
    package_id: UUID = Field(default_factory=uuid4)
    production_package_id: UUID
    hook_analysis: HookAnalysis
    story_report: StoryFlowReport
    retention_report: RetentionReport
    motion_plan: MotionPlan
    subtitle_optimization: SubtitleOptimization
    thumbnail_report: ThumbnailQualityReport
    factuality_report: FactualityReport
    scores: CreativeQualityScores
    score_weights: dict[QualityDimension, float] = Field(default_factory=dict)
    issues: list[CreativeQualityIssue] = Field(default_factory=list)
    gate: CreativeQualityGate
    revision_plan: RevisionPlan
    quality_breakdown: QualityBreakdown | None = None
    applied_revisions: list[str] = Field(default_factory=list)
    current_stage: CreativeQualityStage
    sample_data: bool
    heuristic_label: str = "Internal deterministic quality heuristic"
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    _aware_times = field_validator("created_at", "completed_at")(_aware_optional)


class CreativeQualityStageResult(AuraBaseModel):
    stage: CreativeQualityStage
    employee_id: UUID | None = None
    employee_name: str = Field(min_length=1)
    success: bool
    output_reference: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None

    _aware_times = field_validator("started_at", "completed_at")(_aware)


class CreativeQualityPipelineResult(AuraBaseModel):
    quality_package: CreativeQualityPackage
    original_production_package: ProductionPackage
    revised_production_package: ProductionPackage | None = None
    stage_results: list[CreativeQualityStageResult] = Field(min_length=1)
    runtime_snapshot: dict[str, Any] | None = None
    dashboard_mode: str = Field(min_length=1)
    completed_at: datetime = Field(default_factory=utc_now)

    _aware_completed_at = field_validator("completed_at")(_aware)
