"""Deterministic Intelligence company-mission adapters."""

from __future__ import annotations

from app.dashboard.service import DashboardService


def create_intelligence_demo_dashboard_service() -> DashboardService:
    """Build the cumulative dashboard through the Intelligence stage."""

    from app.runtime.unified_context import DashboardContextStage
    from company_missions.unified_dashboard import (
        create_unified_dashboard_service,
    )

    return create_unified_dashboard_service(
        DashboardContextStage.INTELLIGENCE
    )
