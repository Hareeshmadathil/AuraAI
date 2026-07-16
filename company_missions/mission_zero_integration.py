"""Mission Control-mediated, offline Mission Zero integration."""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.directors.research_director import ResearchDirector
from agents.executive import AuraCEO, AuraCOO
from agents.specialists.trend_hunter import TrendCandidate, TrendHunter
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from core import DepartmentName, MissionObjective, MissionRecord as ExecutiveMission
from creative_quality.models import CreativeQualityPipelineResult
from creative_quality.pipeline import create_creative_quality_pipeline
from intelligence_director.composition import create_demo_result as intelligence_result
from knowledge_manager.composition import create_demo_result as knowledge_result
from mission_control import (
    ApprovalRequest,
    DepartmentBus,
    DepartmentCommand,
    DepartmentResult,
    MissionControlProjection,
    MissionControlService,
    MissionControlStatus,
    MissionRecord,
    RiskLevel,
    TaskRecord,
)
from mission_engine import ArtifactRegistry, InMemoryMissionRepository, MissionManager
from mission_engine.models import Mission, MissionCapability
from private_video_production.composition import PrivateVideoComposition
from private_video_production.pipeline import PrivateVideoProductionPipeline
from production.models import ProductionPackage
from production_connector.loader import MissionPackageLoader
from production_connector.service import ProductionConnectorService
from production_research.service import ProductionResearchService
from providers.composition import create_provider_router
from runtime_engine import RuntimeEventBus, RuntimeStateManager
from web_intelligence.composition import create_offline_demo_service


@dataclass(frozen=True, slots=True)
class MissionZeroIntegrationResult:
    """Complete offline mission state at the founder approval boundary."""

    mission_id: str
    timeline: tuple[str, ...]
    projection: MissionControlProjection
    approval_request: ApprovalRequest
    dashboard_service: DashboardService


class MissionZeroIntegration:
    """Execute existing subsystems only through Mission Control commands."""

    PACKAGE_ID = "f7385664-ac50-4e16-83c1-339781135a0a"

    def __init__(
        self,
        control: MissionControlService,
        *,
        project_root: Path,
    ) -> None:
        self.control = control
        self.root = project_root.resolve()
        self.package_root = (
            self.root / "outputs" / "mission-zero-revision" / self.PACKAGE_ID
        )
        self.context: dict[str, Any] = {}
        self.bus = DepartmentBus()
        self._register_handlers()

    def run(self) -> MissionZeroIntegrationResult:
        """Run deterministically to a pending founder approval and stop."""

        mission = self.control.create_mission(
            MissionRecord(
                title="Mission Zero offline integration",
                objective="Prepare one complete offline content mission for founder review.",
                founder_owner="Hareesh",
                risk=RiskLevel.MEDIUM,
            )
        )
        self.control.transition(mission.mission_id, MissionControlStatus.READY)
        tasks = self._create_tasks(mission)
        self.control.transition(
            mission.mission_id,
            MissionControlStatus.RUNNING,
            stage="executive_review",
        )
        for task in tasks[:-1]:
            command = self.control.dispatch(task.task_id)
            result = self.bus.dispatch(command)
            self.control.accept_result(result)
            if not result.success:
                raise RuntimeError(result.error_code or "Mission Zero task failed.")
            self.control.register_artifact(
                mission_id=mission.mission_id,
                task_id=task.task_id,
                artifact_type=f"{task.idempotency_key}.result",
                location=f"mission-control://{mission.mission_id}/{task.idempotency_key}",
                value=result.payload,
                provenance={"system": task.title, "offline": True},
            )
        approval_task = tasks[-1]
        self.control.next_actions(mission.mission_id)
        approval = self.control.request_approval(approval_task)
        self.control.transition(
            mission.mission_id,
            MissionControlStatus.APPROVAL_REQUIRED,
            stage="founder_approval",
        )
        projection = self.control.projection()
        return MissionZeroIntegrationResult(
            mission_id=str(mission.mission_id),
            timeline=self._timeline(
                self.control.replay(mission.mission_id), mission.mission_id
            ),
            projection=projection,
            approval_request=approval,
            dashboard_service=self._dashboard_service(),
        )

    def _create_tasks(self, mission: MissionRecord) -> list[TaskRecord]:
        definitions = (
            ("CEO Review", DepartmentName.EXECUTIVE, "ceo"),
            ("COO Coordination", DepartmentName.EXECUTIVE, "coo"),
            ("Trend Hunter", DepartmentName.RESEARCH, "trend"),
            ("Intelligence Director", DepartmentName.INTELLIGENCE, "intelligence"),
            ("Knowledge Manager", DepartmentName.INTELLIGENCE, "knowledge"),
            ("Web Intelligence Offline", DepartmentName.RESEARCH, "web"),
            ("Research Department", DepartmentName.RESEARCH, "research"),
            ("Production Research", DepartmentName.PRODUCTION, "production_research"),
            ("Provider Router Offline", DepartmentName.ENGINEERING, "provider_router"),
            ("Script Package", DepartmentName.PRODUCTION, "script"),
            ("Production Connector", DepartmentName.PRODUCTION, "connector"),
            ("Private Video Production Package", DepartmentName.PRODUCTION, "private_video"),
            ("Creative Quality", DepartmentName.CREATIVE_QUALITY, "quality"),
        )
        tasks: list[TaskRecord] = []
        dependency = None
        for title, department, key in definitions:
            value = TaskRecord(
                mission_id=mission.mission_id,
                title=title,
                department=department,
                dependencies=[dependency] if dependency else [],
                idempotency_key=f"mission-zero:{key}",
            )
            self.control.add_task(value)
            tasks.append(value)
            dependency = value.task_id
        quality_hash = self._quality_hash()
        approval = TaskRecord(
            mission_id=mission.mission_id,
            title="Founder Approval",
            department=DepartmentName.EXECUTIVE,
            dependencies=[dependency] if dependency else [],
            idempotency_key="mission-zero:founder-approval",
            consequential=True,
            required_action="approve_mission_zero_content",
            required_artifact_hash=quality_hash,
        )
        self.control.add_task(approval)
        tasks.append(approval)
        return tasks

    def _register_handlers(self) -> None:
        handlers = {
            DepartmentName.EXECUTIVE: self._executive,
            DepartmentName.RESEARCH: self._research,
            DepartmentName.INTELLIGENCE: self._intelligence,
            DepartmentName.PRODUCTION: self._production,
            DepartmentName.ENGINEERING: self._provider_router,
            DepartmentName.CREATIVE_QUALITY: self._quality,
        }
        for department, handler in handlers.items():
            self.bus.register(department, handler)

    def _executive(self, command: DepartmentCommand) -> DepartmentResult:
        if command.idempotency_key.endswith(":ceo"):
            value = ExecutiveMission(
                mission_id=command.mission_id,
                title="Mission Zero offline integration",
                description="Prepare a complete offline founder-review package.",
                lead_department=DepartmentName.RESEARCH,
                objectives=[MissionObjective(description="Reach founder review", success_metric="Pending approval request")],
            )
            decision = AuraCEO().review_mission(value)
            value.approve("CEO approved offline planning only.")
            self.context["executive_mission"] = value
            return self._result(command, {"decision": decision.model_dump(mode="json")})
        workflow = AuraCOO().coordinate_mission(self.context["executive_mission"])
        legacy_repository = InMemoryMissionRepository()
        MissionManager(legacy_repository, ArtifactRegistry())
        legacy = Mission(
            mission_id=command.mission_id,
            title="Mission Zero offline integration",
            objective="Prepare an offline founder-review package.",
            capability=MissionCapability.CONTENT_PIPELINE,
            assigned_departments=[DepartmentName.RESEARCH, DepartmentName.PRODUCTION],
        )
        legacy_repository.save(legacy)
        runtime = RuntimeStateManager(RuntimeEventBus())
        runtime.register_mission(self.context["executive_mission"])
        self.context.update({"legacy_mission": legacy, "runtime": runtime})
        return self._result(command, {"workflow": workflow.record.model_dump(mode="json"), "legacy_mission_id": str(legacy.mission_id)})

    def _research(self, command: DepartmentCommand) -> DepartmentResult:
        key = command.idempotency_key
        if key.endswith(":trend"):
            opportunity = TrendHunter().rank_candidates([TrendCandidate(name="Responsible AI workflows",demand_score=72,trend_velocity_score=68,monetization_score=60,competition_score=45,production_difficulty_score=30,evidence=["Deterministic offline fixture"],risks=["Live validation required"])])[0]
            self.context["trend"] = opportunity
            return self._result(command, opportunity.model_dump(mode="json"))
        if key.endswith(":web"):
            state = create_offline_demo_service().dashboard_state()
            self.context["web"] = state
            return self._result(command, state.model_dump(mode="json"))
        plan = ResearchDirector().create_research_plan(self.context["executive_mission"])
        self.context["research"] = plan
        return self._result(command, plan.model_dump(mode="json"))

    def _intelligence(self, command: DepartmentCommand) -> DepartmentResult:
        if command.idempotency_key.endswith(":intelligence"):
            value = intelligence_result()
            self.context["intelligence"] = value
        else:
            value = knowledge_result()
            self.context["knowledge"] = value
        return self._result(command, value.model_dump(mode="json"))

    def _production(self, command: DepartmentCommand) -> DepartmentResult:
        key = command.idempotency_key
        if key.endswith(":production_research"):
            value = ProductionResearchService().build_report()
        elif key.endswith(":script"):
            value = self._json("script/script-v2.json")
        elif key.endswith(":connector"):
            package = MissionPackageLoader(self.root).load(self.package_root)
            value = ProductionConnectorService(package).status()
        else:
            composition = PrivateVideoComposition.create(self.root / "outputs" / "private-video")
            pipeline = PrivateVideoProductionPipeline(voice_service=composition.voice_service,capabilities=composition.capabilities,ffmpeg_runner=None)
            value, _ = pipeline.prepare(self.package_root, self.root / "outputs" / "private-video", export=False)
        self.context[key] = value
        payload = value if isinstance(value, dict) else value.model_dump(mode="json")
        return self._result(command, payload)

    def _provider_router(self, command: DepartmentCommand) -> DepartmentResult:
        state = create_provider_router().build_state()
        self.context["provider_router"] = state
        return self._result(command, state.model_dump(mode="json"))

    def _quality(self, command: DepartmentCommand) -> DepartmentResult:
        package = ProductionPackage.model_validate(
            self._json("production/revised/production-package.json")
        )
        operation = create_creative_quality_pipeline().run(package)
        if not operation.success:
            return DepartmentResult(
                command_id=command.command_id,
                mission_id=command.mission_id,
                task_id=command.task_id,
                success=False,
                error_code=operation.error_code,
            )
        value = CreativeQualityPipelineResult.model_validate(
            operation.data["creative_quality_pipeline_result"]
        )
        self.context["quality"] = value.quality_package
        return self._result(
            command, value.quality_package.model_dump(mode="json")
        )

    def _dashboard_service(self) -> DashboardService:
        return DashboardService(
            mode=DashboardMode.DEMO,
            data_label="MISSION CONTROL / OFFLINE MISSION ZERO",
            missions=[self.context["legacy_mission"]],
        )

    def _json(self, relative: str) -> dict[str, Any]:
        return json.loads((self.package_root / relative).read_text(encoding="utf-8"))

    def _quality_hash(self) -> str:
        target = self.package_root / "quality/revised/creative-quality.json"
        return hashlib.sha256(target.read_bytes()).hexdigest()

    @staticmethod
    def _result(command: DepartmentCommand, payload: dict[str, Any]) -> DepartmentResult:
        return DepartmentResult(command_id=command.command_id,mission_id=command.mission_id,task_id=command.task_id,success=True,payload=payload)

    @staticmethod
    def _timeline(events, mission_id) -> tuple[str, ...]:
        labels = {
            "mission.created": "Mission Created",
            "approval.requested": "Waiting For Founder Approval",
        }
        values=[]
        for event in events:
            if event.mission_id != mission_id: continue
            if event.event_type in labels: values.append(labels[event.event_type])
            elif event.event_type == "task.completed":
                values.append(f"{event.payload['title']} Complete")
        return tuple(values)
