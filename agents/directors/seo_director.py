"""SEO Director for AuraAI Intelligence Department v1."""

from __future__ import annotations

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from intelligence.providers import IntelligenceProvider
from intelligence.task_inputs import require_niche


class SEODirector(BaseEmployee):
    """Own deterministic search positioning before Production begins."""

    def __init__(self, provider: IntelligenceProvider) -> None:
        super().__init__(
            name="Atlas",
            job_title="SEO Director",
            department=DepartmentName.INTELLIGENCE,
            description="Creates provider-neutral search strategy intelligence.",
        )
        self.provider = provider

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Create a typed SEO report from an explicit niche."""

        report = self.provider.build_seo_report(require_niche(task))
        return OperationResult.ok(
            "SEO intelligence completed.",
            data={"seo_report": report.model_dump(mode="json")},
        )
