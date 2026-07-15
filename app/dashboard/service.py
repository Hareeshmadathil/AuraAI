"""Dashboard snapshot assembly without hidden runtime state."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from app.dashboard.models import (
    ActivityEventSummary,
    ActivityEventType,
    DashboardMetric,
    DashboardMode,
    DashboardSnapshot,
    EmployeeGroup,
    EmployeeStatusSummary,
    ExecutiveDecisionSummary,
    MissionStatusSummary,
    MissionArtifactSummary,
    SystemHealthSummary,
    ProductionStatusSummary,
    RenderArtifactSummary,
    RenderStatusSummary,
    WorkflowStatusSummary,
    classify_employee_group,
)
from core.constants import (
    AgentStatus,
    DecisionOutcome,
    JobStatus,
    MissionStatus,
)
from core.decision import DecisionRecord
from core.mission import MissionRecord
from core.models import AgentIdentity, WorkflowRecord
from mission_engine.models import Mission, MissionExecutionStatus
from production.models import ProductionPackage
from production.rendering.models import LocalRenderResult, RenderedArtifact
from intelligence.models import IntelligencePackage
from creative_quality.models import CreativeQualityPackage
from analytics.models import AnalyticsReport, LearningReport
from distribution.models import DistributionPackage
from providers.models import ProviderState


class DashboardService:
    """Build dashboard snapshots from explicitly supplied AuraAI state."""

    def __init__(
        self,
        *,
        mode: DashboardMode = DashboardMode.EMPTY,
        data_label: str | None = None,
        employees: Iterable[AgentIdentity | Any] = (),
        missions: Iterable[MissionRecord | Mission | MissionStatusSummary] = (),
        decisions: Iterable[DecisionRecord | ExecutiveDecisionSummary] = (),
        workflows: Iterable[WorkflowRecord | Any] = (),
        system_health: SystemHealthSummary | None = None,
        activity: Iterable[ActivityEventSummary] = (),
        production_package: ProductionPackage | ProductionStatusSummary | None = None,
        local_render_result: LocalRenderResult | None = None,
        intelligence_package: IntelligencePackage | None = None,
        niche_discovery: dict[str, Any] | None = None,
        creative_quality_package: CreativeQualityPackage | None = None,
        distribution_package: DistributionPackage | None = None,
        analytics_report: AnalyticsReport | None = None,
        learning_report: LearningReport | None = None,
        provider_state: ProviderState | None = None,
        real_content_pilot: dict[str, Any] | None = None,
        first_content_mission: dict[str, Any] | None = None,
        private_video_production: dict[str, Any] | None = None,
    ) -> None:
        """Store explicit state collections for snapshot generation."""

        self._mode = mode
        self._data_label = data_label or self._default_label(mode)
        self._employees = tuple(employees)
        self._missions = tuple(missions)
        self._decisions = tuple(decisions)
        self._workflows = tuple(workflows)
        self._system_health = system_health or SystemHealthSummary()
        self._activity = tuple(activity)
        self._production_package = production_package
        self._local_render_result = local_render_result
        self._render_artifacts = self._index_render_artifacts(local_render_result)
        self._intelligence_package = intelligence_package
        self._niche_discovery = niche_discovery
        self._creative_quality_package = creative_quality_package
        self._distribution_package = distribution_package
        self._analytics_report = analytics_report
        self._learning_report = learning_report
        self._provider_state = provider_state or ProviderState()
        self._real_content_pilot = real_content_pilot
        self._first_content_mission = first_content_mission
        self._private_video_production = private_video_production

    def build_snapshot(self) -> DashboardSnapshot:
        """Create a validated point-in-time dashboard snapshot."""

        employees = [
            self._summarize_employee(employee)
            for employee in self._employees
        ]
        missions = [
            self._summarize_mission(mission)
            for mission in self._missions
        ]
        sorted_decisions = sorted(
            self._decisions,
            key=lambda item: item.created_at,
            reverse=True,
        )
        decisions = [
            self._summarize_decision(decision)
            for decision in sorted_decisions
        ]
        workflows = [
            self._summarize_workflow(workflow)
            for workflow in self._workflows
        ]

        status_counts = Counter(employee.status for employee in employees)
        active_missions = self._count_active_missions(missions)
        pending_decisions = sum(
            decision.outcome == DecisionOutcome.PENDING
            for decision in decisions
        )
        active_workflows = sum(
            workflow.status == JobStatus.RUNNING
            for workflow in workflows
        )
        employees_working = status_counts[AgentStatus.WORKING]

        return DashboardSnapshot(
            mode=self._mode,
            data_label=self._data_label,
            active_missions=active_missions,
            employees_working=employees_working,
            employees_idle=status_counts[AgentStatus.IDLE],
            pending_decisions=pending_decisions,
            active_workflows=active_workflows,
            employee_status_counts=dict(status_counts),
            metrics=self._build_metrics(
                active_missions=active_missions,
                employees_working=employees_working,
                pending_decisions=pending_decisions,
                active_workflows=active_workflows,
            ),
            employees=employees,
            executives=self._employees_in_group(
                employees,
                EmployeeGroup.EXECUTIVE,
            ),
            directors=self._employees_in_group(
                employees,
                EmployeeGroup.DIRECTOR,
            ),
            specialists=self._employees_in_group(
                employees,
                EmployeeGroup.SPECIALIST,
            ),
            missions=missions,
            workflows=workflows,
            recent_decisions=decisions[:10],
            activity=self._build_activity(sorted_decisions),
            system_health=self._system_health,
            production=self._summarize_production(self._production_package),
            render=self._summarize_render(self._local_render_result),
            intelligence=self._intelligence_package,
            niche_discovery=self._niche_discovery,
            creative_quality=self._creative_quality_package,
            distribution=self._distribution_package,
            analytics=self._analytics_report,
            learning=self._learning_report,
            providers=self._provider_state,
            real_content_pilot=self._real_content_pilot,
            first_content_mission=self._first_content_mission,
            private_video_production=self._private_video_production,
        )

    def get_render_artifact(self, artifact_id: UUID) -> RenderedArtifact | None:
        """Resolve only a registered artifact inside its configured output root."""

        artifact = self._render_artifacts.get(artifact_id)
        if artifact is None or self._local_render_result is None:
            return None
        root = self._local_render_result.export_manifest.settings.output_root.resolve()
        try:
            artifact.path.resolve().relative_to(root)
        except ValueError:
            return None
        return artifact if artifact.path.is_file() else None

    @staticmethod
    def _index_render_artifacts(
        result: LocalRenderResult | None,
    ) -> dict[UUID, RenderedArtifact]:
        if result is None:
            return {}
        return {
            artifact.artifact_id: artifact
            for artifact in result.exported_artifacts
        }

    @staticmethod
    def _summarize_render(
        result: LocalRenderResult | None,
    ) -> RenderStatusSummary | None:
        if result is None:
            return None
        manifest = result.export_manifest
        return RenderStatusSummary(
            production_package_id=result.production_package_id,
            manifest_id=manifest.manifest_id,
            status=manifest.overall_status.value,
            engine=manifest.render_engine.value,
            artifacts=[
                RenderArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    artifact_type=artifact.artifact_type.value,
                    file_name=artifact.path.name,
                    mime_type=artifact.mime_type,
                    size_bytes=artifact.size_bytes,
                    duration_seconds=artifact.duration_seconds,
                    width=artifact.width,
                    height=artifact.height,
                    checksum_sha256=artifact.checksum_sha256 or "unavailable",
                    review_required=artifact.review_required,
                    published=artifact.published,
                )
                for artifact in result.exported_artifacts
            ],
            warnings=manifest.warnings,
            review_required=manifest.review_required,
            publish_allowed=manifest.publish_allowed,
            sample_data=manifest.settings.sample_data,
        )

    @staticmethod
    def _summarize_production(
        value: ProductionPackage | ProductionStatusSummary | None,
    ) -> ProductionStatusSummary | None:
        """Create a truthful production projection without media claims."""

        if value is None or isinstance(value, ProductionStatusSummary):
            return value
        counts: dict[str, int] = {}
        for asset in value.short_form_package.assets:
            key = asset.platform.value
            counts[key] = counts.get(key, 0) + 1
        report = value.quality_report
        return ProductionStatusSummary(
            package_id=value.package_id,
            brand_name=value.input.brand_name,
            topic=value.input.topic,
            working_title=value.input.working_title,
            current_stage=value.current_stage.value,
            completed_stages=[stage.value for stage in value.completed_stages],
            selected_style=value.brief.selected_style.value,
            content_brief_summary=value.brief.core_message,
            script_word_count=value.script.word_count,
            storyboard_scene_count=len(value.storyboard.scenes),
            visual_request_count=len(value.visual_plan.requests),
            voice_segment_count=len(value.voiceover_plan.segments),
            thumbnail_concepts=[
                concept.concept_name for concept in value.thumbnail_plan.concepts
            ],
            short_form_counts=counts,
            subtitle_status="PLANNED / IN-MEMORY / NOT BURNED IN",
            assembly_status=value.assembly_manifest.render_status.value,
            quality_score=report.score_percentage if report else None,
            blockers=list(report.blocking_issues) if report else [],
            warnings=[*value.warnings, *(report.warnings if report else [])],
            founder_approval_status=value.approval_status.value,
            sample_data=value.input.sample_data,
            media_rendered=False,
        )

    @staticmethod
    def _summarize_employee(employee: AgentIdentity | Any) -> (
        EmployeeStatusSummary
    ):
        """Normalize an AgentIdentity or BaseEmployee-like object."""

        if isinstance(employee, EmployeeStatusSummary):
            return employee
        identity_value = getattr(employee, "identity", employee)
        identity = AgentIdentity.model_validate(identity_value)
        return EmployeeStatusSummary(
            agent_id=identity.agent_id,
            name=identity.name,
            job_title=identity.job_title,
            department=identity.department,
            status=identity.status,
            enabled=identity.enabled,
            group=DashboardService._classify_employee(identity),
        )

    @staticmethod
    def _classify_employee(identity: AgentIdentity) -> EmployeeGroup:
        """Classify an employee from existing identity information."""

        return classify_employee_group(identity.department, identity.job_title)

    @staticmethod
    def _employees_in_group(
        employees: list[EmployeeStatusSummary],
        group: EmployeeGroup,
    ) -> list[EmployeeStatusSummary]:
        """Return employees belonging to one organizational level."""

        return [employee for employee in employees if employee.group == group]

    @staticmethod
    def _summarize_mission(
        mission: MissionRecord | Mission | MissionStatusSummary,
    ) -> MissionStatusSummary:
        """Convert a mission into dashboard-safe data."""

        if isinstance(mission, MissionStatusSummary):
            return mission
        if isinstance(mission, Mission):
            lead_department = (
                mission.assigned_departments[0]
                if mission.assigned_departments
                else None
            )
            return MissionStatusSummary(
                mission_id=mission.mission_id,
                title=mission.title,
                description=mission.objective,
                objective=mission.objective,
                capability=mission.capability.value,
                status=mission.status,
                priority=mission.priority,
                lead_department=lead_department,
                progress_percentage=mission.progress_percentage,
                founder_approval_state=(
                    mission.founder_approval_state.value
                ),
                assigned_departments=mission.assigned_departments,
                assigned_employees=[
                    employee.employee_name
                    for employee in mission.assigned_employees
                ],
                generated_artifacts=[
                    MissionArtifactSummary(
                        artifact_id=artifact.artifact_id,
                        artifact_type=artifact.artifact_type.value,
                        name=artifact.name,
                        summary=artifact.summary,
                    )
                    for artifact in mission.produced_artifacts
                ],
            )
        return MissionStatusSummary(
            mission_id=mission.mission_id,
            title=mission.title,
            description=mission.description,
            status=mission.status,
            priority=mission.priority,
            lead_department=mission.lead_department,
            progress_percentage=mission.progress_percentage,
        )

    @staticmethod
    def _summarize_decision(
        decision: DecisionRecord | ExecutiveDecisionSummary,
    ) -> ExecutiveDecisionSummary:
        """Convert a decision into dashboard-safe data."""

        if isinstance(decision, ExecutiveDecisionSummary):
            return decision

        return ExecutiveDecisionSummary(
            decision_id=decision.decision_id,
            title=decision.title,
            decision_type=decision.decision_type,
            outcome=decision.outcome,
            decision_maker_name=decision.decision_maker_name,
            requires_user_confirmation=(
                decision.requires_user_confirmation
            ),
            user_confirmed=decision.user_confirmed,
            created_at=decision.created_at,
        )

    @staticmethod
    def _summarize_workflow(
        workflow: WorkflowRecord | Any,
    ) -> WorkflowStatusSummary:
        """Normalize a WorkflowRecord or BaseWorkflow-like object."""

        if isinstance(workflow, WorkflowStatusSummary):
            return workflow
        record_value = getattr(workflow, "record", workflow)
        record = WorkflowRecord.model_validate(record_value)
        progress_value = getattr(workflow, "progress_percentage", None)
        progress = (
            float(progress_value)
            if progress_value is not None
            else DashboardService._workflow_record_progress(record)
        )
        return WorkflowStatusSummary(
            workflow_id=record.workflow_id,
            name=record.name,
            description=record.description,
            status=record.status,
            progress_percentage=progress,
            task_count=len(record.task_ids),
        )

    @staticmethod
    def _workflow_record_progress(record: WorkflowRecord) -> float:
        """Infer safe progress when only a WorkflowRecord is supplied."""

        if record.status == JobStatus.COMPLETED:
            return 100.0
        return 0.0

    @staticmethod
    def _count_active_missions(
        missions: list[MissionStatusSummary],
    ) -> int:
        """Count missions that are being planned or executed."""

        active_statuses = {
            MissionStatus.PLANNING,
            MissionStatus.ACTIVE,
            MissionStatus.PAUSED,
            MissionExecutionStatus.PLANNING,
            MissionExecutionStatus.RESEARCH,
            MissionExecutionStatus.SEO,
            MissionExecutionStatus.SCRIPT,
            MissionExecutionStatus.FOUNDER_REVIEW,
        }
        return sum(mission.status in active_statuses for mission in missions)

    def _build_activity(
        self,
        sorted_decisions: list[DecisionRecord],
    ) -> list[ActivityEventSummary]:
        """Create recent activity from explicit state and supplied events."""

        events = list(self._activity)
        events.extend(
            ActivityEventSummary(
                event_id=f"mission:{mission.mission_id}",
                event_type=ActivityEventType.MISSION,
                title=mission.title,
                detail=(
                    "Mission status is "
                    f"{mission.status.value.replace('_', ' ')}."
                ),
                occurred_at=mission.updated_at,
            )
            for mission in self._missions
            if isinstance(mission, (MissionRecord, Mission))
        )
        events.extend(
            ActivityEventSummary(
                event_id=f"decision:{decision.decision_id}",
                event_type=ActivityEventType.DECISION,
                title=decision.title,
                detail=(
                    "Executive decision is "
                    f"{decision.outcome.value.replace('_', ' ')}."
                ),
                occurred_at=getattr(decision, "updated_at", decision.created_at),
            )
            for decision in sorted_decisions
        )

        for workflow in self._workflows:
            if isinstance(workflow, WorkflowStatusSummary):
                continue
            record_value = getattr(workflow, "record", workflow)
            record = WorkflowRecord.model_validate(record_value)
            events.append(
                ActivityEventSummary(
                    event_id=f"workflow:{record.workflow_id}",
                    event_type=ActivityEventType.WORKFLOW,
                    title=record.name,
                    detail=(
                        "Workflow status is "
                        f"{record.status.value.replace('_', ' ')}."
                    ),
                    occurred_at=record.updated_at,
                )
            )

        return sorted(
            events,
            key=lambda event: event.occurred_at,
            reverse=True,
        )[:20]

    @staticmethod
    def _default_label(mode: DashboardMode) -> str:
        """Return a clear label for the dashboard data source."""

        return {
            DashboardMode.EMPTY: "EMPTY STATE",
            DashboardMode.DEMO: "DEMO / LOCAL SAMPLE DATA",
            DashboardMode.INJECTED: "INJECTED RUNTIME STATE",
        }[mode]

    @staticmethod
    def _build_metrics(
        *,
        active_missions: int,
        employees_working: int,
        pending_decisions: int,
        active_workflows: int,
    ) -> list[DashboardMetric]:
        """Build the stable set of command-center metric cards."""

        return [
            DashboardMetric(
                key="active_missions",
                label="Active Missions",
                value=active_missions,
                description="Missions being planned or executed.",
            ),
            DashboardMetric(
                key="employees_working",
                label="Employees Working",
                value=employees_working,
                description="AI employees currently performing tasks.",
            ),
            DashboardMetric(
                key="pending_decisions",
                label="Pending Decisions",
                value=pending_decisions,
                description="Executive decisions awaiting an outcome.",
            ),
            DashboardMetric(
                key="active_workflows",
                label="Active Workflows",
                value=active_workflows,
                description="Operational workflows currently running.",
            ),
        ]
