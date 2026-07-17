"""Normal application composition lifecycle for AuraAI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.employee_registry import EmployeeRegistry
from app.dashboard.service import DashboardService
from app.runtime.company_roster import CompanyRoster, create_company_roster
from app.runtime.runtime_dashboard import create_runtime_dashboard_service
from config.settings import DATABASE_DIR
from mission_control.repository import SQLiteMissionControlRepository
from mission_control.service import MissionControlService
from runtime_engine.employee_dispatcher import EmployeeDispatcher
from runtime_engine.runtime_manager import MissionRuntimeManager


DEFAULT_MISSION_CONTROL_DATABASE = DATABASE_DIR / "mission-control.db"


@dataclass(frozen=True, slots=True)
class RuntimeApplicationServices:
    """Application-scoped services created once by the composition root."""

    roster: CompanyRoster
    employee_registry: EmployeeRegistry
    mission_control_service: MissionControlService
    runtime_manager: MissionRuntimeManager
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
    runtime_manager = MissionRuntimeManager(
        mission_control_service,
        EmployeeDispatcher(employee_registry),
    )
    dashboard_service = create_runtime_dashboard_service(
        roster=roster,
        mission_control_service=mission_control_service,
    )
    return RuntimeApplicationServices(
        roster=roster,
        employee_registry=employee_registry,
        mission_control_service=mission_control_service,
        runtime_manager=runtime_manager,
        dashboard_service=dashboard_service,
    )
