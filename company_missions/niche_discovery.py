"""End-to-end deterministic niche discovery company mission."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from agents.base_employee import BaseEmployee
from agents.directors import ResearchDirector, StrategyDirector
from agents.executive import AuraCEO, AuraCOO
from agents.specialists import TrendHunter, TrendOpportunity
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from core import (
    DecisionOutcome,
    DecisionRecord,
    DepartmentName,
    MissionRecord,
    OperationResult,
    TaskPriority,
    TaskRecord,
    utc_now,
)
from marketing import MarketingDirector
from runtime_engine.dashboard_adapter import create_dashboard_service_from_runtime
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.models import RuntimeEventSeverity, RuntimeEventType, RuntimeMode
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager

from company_missions.fixtures import create_sample_niche_discovery_input
from company_missions.models import (
    NicheDiscoveryInput,
    NicheDiscoveryResult,
    NicheDiscoveryStageResult,
)


class NicheDiscoveryPipeline:
    """Coordinate existing AuraAI employees through one company mission."""

    def __init__(
        self,
        orchestrator: RuntimeOrchestrator,
        ceo: AuraCEO,
        coo: AuraCOO,
        research_director: ResearchDirector,
        trend_hunter: TrendHunter | None,
        strategy_director: StrategyDirector | None = None,
        marketing_director: MarketingDirector | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.ceo = ceo
        self.coo = coo
        self.research_director = research_director
        self.trend_hunter = trend_hunter
        self.strategy_director = strategy_director
        self.marketing_director = marketing_director

    def run(
        self,
        pipeline_input: NicheDiscoveryInput,
        *,
        user_confirmed: bool = False,
    ) -> OperationResult:
        """Run the bounded deterministic mission from review to completion."""

        if self.trend_hunter is None:
            return OperationResult.failure(
                "Trend Hunter dependency is required.",
                error_code="MISSING_EMPLOYEE_DEPENDENCY",
            )
        if not pipeline_input.candidate_niches:
            return OperationResult.failure(
                "At least one niche candidate is required.",
                error_code="EMPTY_CANDIDATES",
            )

        self._ensure_runtime_started()
        self._register_participants()
        mission = self._build_mission(pipeline_input)
        stages: list[NicheDiscoveryStageResult] = []

        review_result, review_stage = self._execute_stage(
            stage_name="executive_review",
            employee=self.ceo,
            task=TaskRecord(
                title="Review niche discovery mission",
                department=DepartmentName.EXECUTIVE,
                input_data={"mission": mission},
            ),
            mission_id=mission.mission_id,
        )
        stages.append(review_stage)
        if not review_result.success:
            return self._stage_failure(review_result, stages)

        decision = DecisionRecord.model_validate(
            review_result.data["decision"]
        )
        self.orchestrator.state_manager.register_decision(decision)
        if decision.outcome != DecisionOutcome.APPROVED:
            self.orchestrator.state_manager.register_mission(mission)
            self.orchestrator.event_bus.emit(
                RuntimeEventType.WARNING,
                "Executive review did not approve the mission.",
                mission_id=mission.mission_id,
                severity=RuntimeEventSeverity.WARNING,
            )
            return OperationResult.failure(
                "Executive decision did not approve niche discovery.",
                error_code="EXECUTIVE_APPROVAL_REQUIRED",
                data={"stages": self._serialize_stages(stages)},
            )
        if decision.requires_user_confirmation and not user_confirmed:
            self.orchestrator.state_manager.register_mission(mission)
            return OperationResult.failure(
                "Explicit user confirmation is required.",
                error_code="USER_CONFIRMATION_REQUIRED",
                data={
                    "decision": decision.model_dump(mode="json"),
                    "stages": self._serialize_stages(stages),
                },
            )
        if decision.requires_user_confirmation:
            decision.confirm_by_user()
            self.orchestrator.state_manager.register_decision(
                decision,
                replace=True,
            )

        mission.approve("Approved through explicit niche discovery review.")
        workflow = self.orchestrator.start_mission(mission)
        workflow.start()
        mission.activate()
        self._sync_runtime(mission, workflow)

        research_result, research_stage = self._execute_stage(
            stage_name="research_planning",
            employee=self.research_director,
            task=TaskRecord(
                title="Create niche discovery research plan",
                department=DepartmentName.RESEARCH,
                input_data={"mission": mission},
            ),
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
        )
        stages.append(research_stage)
        if not research_result.success:
            return self._fail_running_mission(
                mission, workflow, research_result, stages
            )
        self._complete_next_workflow_step(workflow, research_result.data)

        candidates = [
            candidate.to_trend_candidate()
            for candidate in pipeline_input.candidate_niches
        ]
        trend_result, trend_stage = self._execute_stage(
            stage_name="trend_ranking",
            employee=self.trend_hunter,
            task=TaskRecord(
                title="Rank deterministic niche candidates",
                department=DepartmentName.RESEARCH,
                input_data={"candidates": candidates},
            ),
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
        )
        stages.append(trend_stage)
        if not trend_result.success:
            return self._fail_running_mission(
                mission, workflow, trend_result, stages
            )
        self._complete_next_workflow_step(workflow, trend_result.data)

        ranked = [
            TrendOpportunity.model_validate(value)
            for value in trend_result.data["opportunities"]
        ]
        selected = ranked[0]
        self.orchestrator.event_bus.emit(
            RuntimeEventType.DECISION_RECORDED,
            f"Niche selected: {selected.name}.",
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
            metadata={"selected_niche": selected.name},
        )

        strategy_summary = self._strategy_summary(selected, pipeline_input)
        if self.strategy_director is not None:
            strategy_result, strategy_stage = self._execute_stage(
                stage_name="strategy_planning",
                employee=self.strategy_director,
                task=TaskRecord(
                    title="Create selected niche strategy",
                    department=DepartmentName.STRATEGY,
                    input_data={"mission": mission},
                ),
                mission_id=mission.mission_id,
                workflow_id=workflow.workflow_id,
            )
            stages.append(strategy_stage)
            if not strategy_result.success:
                return self._fail_running_mission(
                    mission, workflow, strategy_result, stages
                )

        marketing_readiness = False
        if self.marketing_director is not None:
            marketing_result, marketing_stage = self._execute_stage(
                stage_name="marketing_planning",
                employee=self.marketing_director,
                task=TaskRecord(
                    title="Create selected niche marketing plan",
                    department=DepartmentName.MARKETING,
                    input_data={"mission": mission},
                ),
                mission_id=mission.mission_id,
                workflow_id=workflow.workflow_id,
            )
            stages.append(marketing_stage)
            if not marketing_result.success:
                return self._fail_running_mission(
                    mission, workflow, marketing_result, stages
                )
            marketing_readiness = True

        approval_step = workflow.steps[-1]
        approval_step.approve()
        workflow.start_step(approval_step.step_id)
        workflow.complete_step(
            approval_step.step_id,
            output_data={"selected_niche": selected.name},
        )
        for objective in mission.objectives:
            objective.mark_achieved()
        mission.complete()
        self._sync_runtime(mission, workflow)
        self.orchestrator.state_manager.set_health_component(
            "niche_discovery_pipeline",
            "operational",
            "Deterministic sample mission completed successfully.",
        )
        self.orchestrator.event_bus.emit(
            RuntimeEventType.MISSION_COMPLETED,
            f"Niche discovery completed: {selected.name}.",
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
            metadata={"selected_niche": selected.name},
        )

        research_plan_id = UUID(
            research_result.data["research_plan"]["research_plan_id"]
        )
        final_result = NicheDiscoveryResult(
            mission_id=mission.mission_id,
            selected_niche=selected,
            ranked_candidates=ranked,
            research_plan_id=research_plan_id,
            strategy_summary=strategy_summary,
            marketing_readiness=marketing_readiness,
            confidence_score=round(selected.opportunity_score / 100, 4),
            warnings=[
                "Candidate evidence is deterministic sample data, not live research."
            ],
            stages=stages,
            completed_at=utc_now(),
        )
        return OperationResult.ok(
            "Niche discovery pipeline completed.",
            data={
                "niche_discovery_result": final_result.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
                "runtime_snapshot": self.orchestrator.snapshot().model_dump(
                    mode="json"
                ),
            },
        )

    def _register_participants(self) -> None:
        registered = {
            employee.agent_id
            for employee in self.orchestrator.list_registered_employees()
        }
        participants: Iterable[BaseEmployee | None] = (
            self.ceo,
            self.coo,
            self.research_director,
            self.trend_hunter,
            self.strategy_director,
            self.marketing_director,
        )
        for employee in participants:
            if employee is not None and employee.agent_id not in registered:
                self.orchestrator.register_employee(employee)
                registered.add(employee.agent_id)

    def _ensure_runtime_started(self) -> None:
        mode = self.orchestrator.state_manager.mode
        if mode == RuntimeMode.STOPPED:
            self.orchestrator.start()
        elif mode == RuntimeMode.PAUSED:
            self.orchestrator.resume()

    @staticmethod
    def _build_mission(pipeline_input: NicheDiscoveryInput) -> MissionRecord:
        mission = MissionRecord(
            title=pipeline_input.mission_title,
            description=pipeline_input.business_goal,
            priority=TaskPriority.HIGH,
            lead_department=DepartmentName.RESEARCH,
            context={
                "target_market": pipeline_input.target_market,
                "preferred_platforms": [
                    platform.value
                    for platform in pipeline_input.preferred_platforms
                ],
                "constraints": list(pipeline_input.constraints),
                "data_source": "deterministic_sample",
            },
        )
        mission.add_objective(
            description="Create a structured niche research plan.",
            success_metric="One validated research plan",
            target_value="1 plan",
        )
        mission.add_objective(
            description="Rank supplied niche candidates transparently.",
            success_metric="All supplied candidates ranked",
            target_value=str(len(pipeline_input.candidate_niches)),
        )
        mission.add_objective(
            description="Select one niche and assess marketing readiness.",
            success_metric="One selected niche",
            target_value="1 niche",
        )
        return mission

    def _execute_stage(
        self,
        *,
        stage_name: str,
        employee: BaseEmployee,
        task: TaskRecord,
        mission_id: UUID,
        workflow_id: UUID | None = None,
    ) -> tuple[OperationResult, NicheDiscoveryStageResult]:
        started_at = utc_now()
        self.orchestrator.event_bus.emit(
            RuntimeEventType.TASK_STARTED,
            f"{stage_name.replace('_', ' ').title()} started.",
            mission_id=mission_id,
            workflow_id=workflow_id,
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=employee.department,
            metadata={"stage": stage_name},
        )
        employee.accept_task(task)
        self.orchestrator.state_manager.update_employee_state(
            employee.agent_id,
            status=employee.status,
            current_task_id=task.task_id,
            current_task_title=task.title,
            current_mission_id=mission_id,
        )
        result = employee.execute_current_task()
        completed_at = utc_now()
        event_type = (
            RuntimeEventType.TASK_COMPLETED
            if result.success
            else RuntimeEventType.TASK_FAILED
        )
        self.orchestrator.event_bus.emit(
            event_type,
            f"{stage_name.replace('_', ' ').title()} "
            f"{'completed' if result.success else 'failed'}.",
            mission_id=mission_id,
            workflow_id=workflow_id,
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=employee.department,
            severity=(
                RuntimeEventSeverity.INFO
                if result.success
                else RuntimeEventSeverity.ERROR
            ),
            metadata={"stage": stage_name},
        )
        if employee.current_task is not None and not employee.has_active_task:
            employee.clear_current_task()
        self.orchestrator.state_manager.update_employee_state(
            employee.agent_id,
            status=employee.status,
            current_task_id=None,
            current_task_title=None,
            current_mission_id=None,
            error_message=None if result.success else result.message,
        )
        stage = NicheDiscoveryStageResult(
            stage_name=stage_name,
            success=result.success,
            employee_name=employee.name,
            department=employee.department,
            output=result.data,
            started_at=started_at,
            completed_at=completed_at,
            error=None if result.success else result.message,
        )
        return result, stage

    def _complete_next_workflow_step(
        self, workflow, output_data: dict[str, Any]
    ) -> None:
        step = workflow.get_ready_steps()[0]
        workflow.start_step(step.step_id)
        workflow.complete_step(step.step_id, output_data=output_data)
        self.orchestrator.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=workflow.progress_percentage,
        )

    def _sync_runtime(self, mission: MissionRecord, workflow) -> None:
        self.orchestrator.state_manager.update_mission_state(
            mission.mission_id,
            status=mission.status,
            progress_percentage=mission.progress_percentage,
            active_workflow_id=workflow.workflow_id,
            started_at=mission.started_at,
            completed_at=mission.completed_at,
        )
        self.orchestrator.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=workflow.progress_percentage,
            started_at=workflow.record.started_at,
            completed_at=workflow.record.completed_at,
        )

    def _fail_running_mission(
        self,
        mission: MissionRecord,
        workflow,
        failure: OperationResult,
        stages: list[NicheDiscoveryStageResult],
    ) -> OperationResult:
        ready = workflow.get_ready_steps()
        if ready:
            workflow.start_step(ready[0].step_id)
            workflow.fail_step(
                ready[0].step_id,
                error_message=failure.message,
            )
        if not mission.is_terminal:
            mission.fail(failure.message)
        self._sync_runtime(mission, workflow)
        return self._stage_failure(failure, stages)

    @staticmethod
    def _stage_failure(
        failure: OperationResult,
        stages: list[NicheDiscoveryStageResult],
    ) -> OperationResult:
        return OperationResult.failure(
            failure.message,
            error_code=failure.error_code or "PIPELINE_STAGE_FAILED",
            data={"stages": NicheDiscoveryPipeline._serialize_stages(stages)},
        )

    @staticmethod
    def _serialize_stages(
        stages: list[NicheDiscoveryStageResult],
    ) -> list[dict[str, Any]]:
        return [stage.model_dump(mode="json") for stage in stages]

    @staticmethod
    def _strategy_summary(selected: TrendOpportunity, value: NicheDiscoveryInput) -> str:
        platforms = ", ".join(platform.value for platform in value.preferred_platforms)
        return (
            f"Prioritize '{selected.name}' for {value.target_market}. "
            f"Its deterministic opportunity score is "
            f"{selected.opportunity_score:.2f}/100. Validate the sample "
            f"assumptions before production and prepare platform roles for "
            f"{platforms}."
        )


def create_niche_discovery_demo_dashboard_service() -> DashboardService:
    """Execute the sample pipeline and adapt its runtime snapshot."""

    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    coo = AuraCOO()
    runner = MissionRunner(state, bus)
    orchestrator = RuntimeOrchestrator(bus, state, coo, runner)
    pipeline = NicheDiscoveryPipeline(
        orchestrator=orchestrator,
        ceo=AuraCEO(),
        coo=coo,
        research_director=ResearchDirector(),
        trend_hunter=TrendHunter(),
        strategy_director=StrategyDirector(),
        marketing_director=MarketingDirector(),
    )
    result = pipeline.run(
        create_sample_niche_discovery_input(),
        user_confirmed=True,
    )
    if not result.success:
        raise RuntimeError(result.message)
    return create_dashboard_service_from_runtime(
        orchestrator.snapshot(),
        mode=DashboardMode.DEMO,
        data_label="NICHE DISCOVERY DEMO / DETERMINISTIC SAMPLE DATA",
    )
