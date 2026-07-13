"""Dashboard adapters for local Distribution and Analytics demos."""

from app.dashboard.service import DashboardService
from app.runtime.unified_context import DashboardContextStage


def create_distribution_demo_dashboard_service() -> DashboardService:
    """Build the cumulative demo through deterministic learning."""

    from company_missions.unified_dashboard import create_unified_dashboard_service

    return create_unified_dashboard_service(DashboardContextStage.LEARNING)
