"""Composition root for the real local AuraAI runtime dashboard."""
from __future__ import annotations

from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from app.runtime.company_roster import create_company_roster
from runtime_engine.dashboard_adapter import create_dashboard_service_from_runtime
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.state_manager import RuntimeStateManager


def create_runtime_dashboard_service(
    state_manager: RuntimeStateManager | None = None,
) -> DashboardService:
    """Build a real roster dashboard from the existing runtime projection.

    The runtime starts with no synthetic missions, decisions, or workflows.
    Employee status is sourced from the runtime manager after the canonical
    roster has been registered.
    """

    roster = create_company_roster()
    runtime = state_manager or RuntimeStateManager(RuntimeEventBus())
    if runtime.mode.value == "stopped":
        runtime.start_runtime()
    for employee in roster.employees:
        runtime.register_employee(employee, replace=True)
    return create_dashboard_service_from_runtime(
        runtime.snapshot(),
        mode=DashboardMode.INJECTED,
        data_label="LOCAL RUNTIME STATE",
        company_roster=roster.employees,
    )
