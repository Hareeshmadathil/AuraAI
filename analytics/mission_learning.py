"""Deterministic mission learning over existing Mission Control and Knowledge Manager."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from core import AuraBaseModel, utc_now
from intelligence_director.enums import VerificationStatus
from knowledge_manager.approvals import evidence_hash
from knowledge_manager.enums import (
    ApprovalStatus,
    EvidenceClass,
    FreshnessStatus,
    KnowledgeCategory,
    RetentionAction,
    SourceSystem,
)
from knowledge_manager.models import (
    KnowledgeClaim,
    KnowledgeFreshness,
    KnowledgeIngestionRequest,
    KnowledgeRetentionPolicy,
    KnowledgeSourceReference,
    KnowledgeTopic,
    KnowledgeVersion,
)
from knowledge_manager.normalization import canonical_claim, normalize_text
from knowledge_manager.service import KnowledgeManagerService
from mission_control import MissionControlService
from mission_control.models import (
    ArtifactApprovalState,
    EventRecord,
    MissionControlStatus,
    TaskStatus,
)


class LessonCategory(StrEnum):
    RESEARCH_QUALITY = "research_quality"
    EVIDENCE_QUALITY = "evidence_quality"
    TOPIC_SELECTION = "topic_selection"
    DUPLICATION = "duplication"
    SCRIPT_QUALITY = "script_quality"
    CREATIVE_QUALITY = "creative_quality"
    EXECUTION_RELIABILITY = "execution_reliability"
    FOUNDER_REVISION = "founder_revision"
    WORKFLOW_EFFICIENCY = "workflow_efficiency"
    REVENUE_RELEVANCE = "revenue_relevance"


class LessonImpact(StrEnum):
    POSITIVE = "positive"
    IMPROVEMENT = "improvement"
    RISK = "risk"


class MissionOutcome(AuraBaseModel):
    outcome_id: UUID
    mission_id: UUID
    mission_objective: str
    expected_outcome: str
    actual_outcome: str
    final_mission_status: MissionControlStatus
    quality_result: dict = Field(default_factory=dict)
    founder_decision: str
    revision_count: int = Field(ge=0)
    failed_tasks: list[UUID] = Field(default_factory=list)
    blocked_tasks: list[UUID] = Field(default_factory=list)
    retry_count: int = Field(ge=0)
    execution_duration_seconds: float = Field(ge=0)
    evidence_used: list[UUID] = Field(default_factory=list)
    artifacts_produced: list[UUID] = Field(default_factory=list)
    expected_success_criteria: list[str] = Field(default_factory=list)
    achieved_success_criteria: list[str] = Field(default_factory=list)
    unmet_success_criteria: list[str] = Field(default_factory=list)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class MissionLesson(AuraBaseModel):
    lesson_id: UUID
    source_mission_id: UUID
    category: LessonCategory
    observation: str
    supporting_evidence: list[str]
    confidence: float = Field(ge=0, le=1)
    impact: LessonImpact
    affected_subsystem: str
    recommended_future_behavior: str
    success_metric: str
    freshness_window_days: int = Field(ge=1)
    expires_at: datetime
    provenance: dict
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval_status: ApprovalStatus


class LessonInfluence(AuraBaseModel):
    score_delta: float
    confidence_delta: float
    lesson_ids: list[UUID]
    explanations: list[str]


class MissionLearningService:
    """Create, persist, and retrieve traceable mission lessons."""

    def __init__(
        self,
        *,
        control: MissionControlService,
        knowledge_manager: KnowledgeManagerService,
    ) -> None:
        self.control = control
        self.knowledge = knowledge_manager

    def collect_outcome(
        self,
        mission_id: UUID,
        *,
        actual_outcome: str,
        founder_decision: str,
        revision_count: int = 0,
    ) -> MissionOutcome:
        mission = self.control.repository.get_mission(mission_id)
        if mission is None:
            raise KeyError(f"Unknown mission: {mission_id}")
        tasks = self.control.repository.list_tasks(mission_id)
        artifacts = [
            item
            for item in self.control.repository.list_artifacts(mission_id)
            if not item.artifact_type.startswith("mission_learning.")
        ]
        quality = next(
            (
                item.metadata
                for item in artifacts
                if "quality" in item.artifact_type.casefold()
            ),
            {},
        )
        completed_titles = {
            task.title for task in tasks if task.status == TaskStatus.COMPLETED
        }
        achieved = [
            criterion
            for criterion in mission.success_criteria
            if self._criterion_achieved(criterion, completed_titles, mission.status)
        ]
        payload = {
            "mission_id": str(mission_id),
            "actual_outcome": actual_outcome,
            "founder_decision": founder_decision,
            "revision_count": revision_count,
            "artifacts": [str(item.artifact_id) for item in artifacts],
        }
        digest = self._hash(payload)
        return MissionOutcome(
            outcome_id=uuid5(NAMESPACE_URL, f"mission-outcome:{digest}"),
            mission_id=mission_id,
            mission_objective=mission.objective,
            expected_outcome=mission.expected_outcome,
            actual_outcome=actual_outcome,
            final_mission_status=mission.status,
            quality_result=quality,
            founder_decision=founder_decision,
            revision_count=revision_count,
            failed_tasks=[t.task_id for t in tasks if t.status == TaskStatus.FAILED],
            blocked_tasks=[t.task_id for t in tasks if t.status == TaskStatus.BLOCKED],
            retry_count=sum(max(0, task.attempts - 1) for task in tasks),
            execution_duration_seconds=max(
                0.0, (mission.updated_at - mission.created_at).total_seconds()
            ),
            evidence_used=[
                item.artifact_id
                for item in artifacts
                if any(key in item.artifact_type for key in ("trend", "web", "intelligence"))
            ],
            artifacts_produced=[item.artifact_id for item in artifacts],
            expected_success_criteria=mission.success_criteria,
            achieved_success_criteria=achieved,
            unmet_success_criteria=[
                item for item in mission.success_criteria if item not in achieved
            ],
            content_hash=digest,
        )

    def generate_lessons(self, outcome: MissionOutcome) -> list[MissionLesson]:
        """Generate deterministic positive and improvement lessons."""

        lessons = []
        quality_score = self._quality_score(outcome.quality_result)
        if quality_score >= 75:
            lessons.append(
                self._lesson(
                    outcome,
                    category=LessonCategory.CREATIVE_QUALITY,
                    observation=f"Creative Quality completed with score {quality_score:.2f}.",
                    evidence=[outcome.content_hash],
                    confidence=0.9,
                    impact=LessonImpact.POSITIVE,
                    subsystem="creative_quality",
                    behavior="Favor similarly evidence-bound production patterns.",
                    metric="Future Creative Quality score remains at least 75.",
                )
            )
        if outcome.revision_count > 0:
            lessons.append(
                self._lesson(
                    outcome,
                    category=LessonCategory.FOUNDER_REVISION,
                    observation=f"The mission required {outcome.revision_count} revision cycle(s).",
                    evidence=[outcome.content_hash],
                    confidence=0.85,
                    impact=LessonImpact.IMPROVEMENT,
                    subsystem="production",
                    behavior="Budget one explicit revision pass before founder review.",
                    metric="Reduce unplanned founder revision cycles.",
                )
            )
        if outcome.blocked_tasks or outcome.failed_tasks:
            lessons.append(
                self._lesson(
                    outcome,
                    category=LessonCategory.WORKFLOW_EFFICIENCY,
                    observation="The mission contained blocked or failed workflow tasks.",
                    evidence=[str(item) for item in [*outcome.blocked_tasks, *outcome.failed_tasks]],
                    confidence=0.8,
                    impact=LessonImpact.RISK,
                    subsystem="mission_control",
                    behavior="Increase dependency review before dispatch.",
                    metric="No preventable blocked or failed task in the next mission.",
                )
            )
        for criterion in outcome.unmet_success_criteria:
            lessons.append(
                self._lesson(
                    outcome,
                    category=LessonCategory.EXECUTION_RELIABILITY,
                    observation=f"Success criterion was unmet: {criterion}",
                    evidence=[outcome.content_hash],
                    confidence=0.75,
                    impact=LessonImpact.IMPROVEMENT,
                    subsystem="mission_control",
                    behavior="Reduce confidence until the criterion is demonstrated.",
                    metric=f"Achieve criterion: {criterion}",
                )
            )
        unique = {lesson.content_hash: lesson for lesson in lessons}
        return sorted(unique.values(), key=lambda item: str(item.lesson_id))

    def persist(
        self,
        outcome: MissionOutcome,
        lessons: list[MissionLesson],
    ) -> list[MissionLesson]:
        tasks = self.control.repository.list_tasks(outcome.mission_id)
        task_id = tasks[-1].task_id
        self.control.register_artifact(
            mission_id=outcome.mission_id,
            task_id=task_id,
            artifact_type="mission_learning.outcome",
            location=f"mission-control://{outcome.mission_id}/outcome",
            value=outcome.model_dump(mode="json"),
            provenance={"mission_id": str(outcome.mission_id), "offline": True},
            approval_state=ArtifactApprovalState.NOT_REQUIRED,
        )
        persisted = []
        for lesson in lessons:
            artifact = self.control.register_artifact(
                mission_id=outcome.mission_id,
                task_id=task_id,
                artifact_type="mission_learning.lesson",
                location=f"mission-control://{outcome.mission_id}/lessons/{lesson.lesson_id}",
                value=lesson.model_dump(mode="json"),
                provenance=lesson.provenance,
                approval_state=(
                    ArtifactApprovalState.APPROVED
                    if lesson.approval_status == ApprovalStatus.APPROVED
                    else ArtifactApprovalState.PENDING
                ),
            )
            if lesson.approval_status == ApprovalStatus.APPROVED:
                self.knowledge.ingest(self._knowledge_request(lesson))
                persisted.append(lesson)
                event_type = "lesson.approved_and_stored"
            else:
                event_type = "lesson.approval_required"
            self.control.repository.append_event(
                EventRecord(
                    mission_id=outcome.mission_id,
                    task_id=task_id,
                    event_type=event_type,
                    payload={
                        "lesson_id": str(lesson.lesson_id),
                        "artifact_id": str(artifact.artifact_id),
                    },
                )
            )
        return persisted

    def influence(self) -> LessonInfluence:
        """Return transparent influence from approved, non-expired lessons."""

        if not hasattr(self.knowledge, "repository"):
            return LessonInfluence(
                score_delta=0.0,
                confidence_delta=0.0,
                lesson_ids=[],
                explanations=[],
            )
        delta = 0.0
        confidence = 0.0
        ids = []
        explanations = []
        for version in self.knowledge.repository.list_versions():
            if "mission_learning" not in version.topic.tags:
                continue
            if version.approval_status != ApprovalStatus.APPROVED:
                continue
            if version.freshness.status in {
                FreshnessStatus.STALE,
                FreshnessStatus.EXPIRED,
                FreshnessStatus.ARCHIVED,
                FreshnessStatus.SUPERSEDED,
            }:
                continue
            positive = "impact-positive" in version.topic.tags
            adjustment = 4.0 if positive else -2.0
            delta += adjustment
            confidence += 0.02 if positive else -0.01
            ids.append(version.knowledge_id)
            explanations.append(
                f"Lesson {version.knowledge_id} adjusted score by {adjustment:+.1f}."
            )
        return LessonInfluence(
            score_delta=round(delta, 2),
            confidence_delta=round(confidence, 4),
            lesson_ids=ids,
            explanations=explanations,
        )

    def store_approved_lesson(self, lesson: MissionLesson) -> bool:
        """Store one approved external-outcome lesson through Knowledge Manager."""

        if lesson.approval_status != ApprovalStatus.APPROVED:
            return False
        return bool(self.knowledge.ingest(self._knowledge_request(lesson)).accepted)

    def _lesson(self, outcome, *, category, observation, evidence, confidence, impact, subsystem, behavior, metric):
        identity = uuid5(
            NAMESPACE_URL,
            f"mission-lesson:{outcome.mission_id}:{category.value}:{observation}",
        )
        expires = utc_now() + timedelta(days=180)
        core = {
            "lesson_id": str(identity),
            "source_mission_id": str(outcome.mission_id),
            "category": category.value,
            "observation": observation,
            "supporting_evidence": evidence,
            "impact": impact.value,
            "affected_subsystem": subsystem,
            "recommended_future_behavior": behavior,
            "success_metric": metric,
        }
        return MissionLesson(
            lesson_id=identity,
            source_mission_id=outcome.mission_id,
            category=category,
            observation=observation,
            supporting_evidence=evidence,
            confidence=confidence,
            impact=impact,
            affected_subsystem=subsystem,
            recommended_future_behavior=behavior,
            success_metric=metric,
            freshness_window_days=180,
            expires_at=expires,
            provenance={
                "source_mission_id": str(outcome.mission_id),
                "outcome_hash": outcome.content_hash,
                "artifact_ids": [str(item) for item in outcome.artifacts_produced],
                "evidence_ids": [str(item) for item in outcome.evidence_used],
                "founder_decision": outcome.founder_decision,
            },
            content_hash=self._hash(core),
            approval_status=ApprovalStatus.APPROVED,
        )

    def _knowledge_request(self, lesson: MissionLesson) -> KnowledgeIngestionRequest:
        now = utc_now()
        source = KnowledgeSourceReference(
            source_system=SourceSystem.MISSION_ARTIFACT,
            artifact_id=str(lesson.lesson_id),
            artifact_hash=lesson.content_hash,
            locator=f"mission-control://{lesson.source_mission_id}/lessons/{lesson.lesson_id}",
            evidence_class=EvidenceClass.INTERNAL,
            authority_score=lesson.confidence * 100,
            observed_at=now,
        )
        claim = KnowledgeClaim(
            text=lesson.observation,
            canonical_text=canonical_claim(lesson.observation),
            confidence=lesson.confidence,
            verification_status=VerificationStatus.VERIFIED,
        )
        version = KnowledgeVersion(
            knowledge_id=lesson.lesson_id,
            version=1,
            topic=KnowledgeTopic(
                name=f"Mission lesson: {lesson.affected_subsystem}",
                normalized_name=normalize_text(
                    f"Mission lesson: {lesson.affected_subsystem}"
                ),
                tags=[
                    "mission_learning",
                    f"impact-{lesson.impact.value}",
                    f"category-{lesson.category.value}",
                ],
            ),
            category=KnowledgeCategory.PRODUCTION_LESSON,
            claims=[claim],
            summary=lesson.recommended_future_behavior,
            sources=[source],
            freshness=KnowledgeFreshness(
                observed_at=now,
                valid_from=now,
                last_verified_at=now,
                refresh_after=now + timedelta(days=90),
                expires_at=lesson.expires_at,
                status=FreshnessStatus.FRESH,
            ),
            retention_policy=KnowledgeRetentionPolicy(
                action=RetentionAction.VERIFIED,
                maximum_retention_days=lesson.freshness_window_days,
                founder_approval_required=False,
                rationale="Policy-allowed deterministic mission lesson.",
            ),
            approval_status=lesson.approval_status,
            created_by="Mission Learning V1",
        )
        return KnowledgeIngestionRequest(
            source_system=SourceSystem.MISSION_ARTIFACT,
            source_artifact_id=str(lesson.lesson_id),
            source_artifact_hash=lesson.content_hash,
            proposed_version=version,
            private_data_risk=False,
        )

    @staticmethod
    def _quality_score(value: dict) -> float:
        scores = value.get("scores", {})
        return float(scores.get("overall", value.get("overall_score", 0)))

    @staticmethod
    def _criterion_achieved(criterion, completed_titles, status):
        lowered = criterion.casefold()
        if "quality" in lowered:
            return "Creative Quality" in completed_titles
        if "founder approval" in lowered:
            return status == MissionControlStatus.APPROVAL_REQUIRED
        if "offline stages" in lowered:
            return len(completed_titles) >= 13
        return False

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
