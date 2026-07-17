"""Normal application composition lifecycle for AuraAI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.employee_registry import EmployeeRegistry
from app.dashboard.service import DashboardService
from app.runtime.company_roster import CompanyRoster, create_company_roster
from app.runtime.runtime_dashboard import create_runtime_dashboard_service
from app.runtime.mission_commands import MissionCommandService
from config.settings import DATABASE_DIR
from mission_control.repository import SQLiteMissionControlRepository
from mission_control.service import MissionControlService
from runtime_engine.employee_dispatcher import EmployeeDispatcher
from runtime_engine.runtime_manager import MissionRuntimeManager
from runtime_engine.recovery import RecoveryGate, RestartReconciler


DEFAULT_MISSION_CONTROL_DATABASE = DATABASE_DIR / "mission-control.db"


@dataclass(frozen=True, slots=True)
class RuntimeApplicationServices:
    """Application-scoped services created once by the composition root."""

    roster: CompanyRoster
    employee_registry: EmployeeRegistry
    employee_dispatcher: EmployeeDispatcher
    mission_control_service: MissionControlService
    runtime_manager: MissionRuntimeManager
    mission_command_service: MissionCommandService
    recovery_gate: RecoveryGate
    dashboard_service: DashboardService


def create_runtime_application_services(
    *,
    database_path: Path = DEFAULT_MISSION_CONTROL_DATABASE,
    allowed_root: Path = DATABASE_DIR,
) -> RuntimeApplicationServices:
    """Compose one persistent authority shared by all normal app surfaces."""

    roster = create_company_roster()
    employee_registry = EmployeeRegistry()
    employee_registry.register_many(roster.employees)
    repository = SQLiteMissionControlRepository(
        database_path,
        allowed_root=allowed_root,
    )
    mission_control_service = MissionControlService(repository)
    employee_dispatcher = EmployeeDispatcher(employee_registry)
    recovery_gate = RecoveryGate()
    reconciler = RestartReconciler(mission_control_service)
    runtime_manager = MissionRuntimeManager(
        mission_control_service,
        employee_dispatcher,
        recovery_gate,
        reconciler,
    )
    try:
        runtime_manager.reconcile()
    except Exception:
        # The failed gate remains visible; every mutation command fails closed.
        pass
    mission_command_service = MissionCommandService(runtime_manager)
    dashboard_service = create_runtime_dashboard_service(
        roster=roster,
        mission_control_service=mission_control_service,
        recovery_gate=recovery_gate,
    )
    return RuntimeApplicationServices(
        roster=roster,
        employee_registry=employee_registry,
        employee_dispatcher=employee_dispatcher,
        mission_control_service=mission_control_service,
        runtime_manager=runtime_manager,
        mission_command_service=mission_command_service,
        recovery_gate=recovery_gate,
        dashboard_service=dashboard_service,
    )
