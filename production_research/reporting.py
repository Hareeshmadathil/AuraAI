"""JSON and Markdown exports for AI Production Research."""

from __future__ import annotations

import json
from pathlib import Path

from production_research.models import ProviderResearchReport


class ProductionResearchReporter:
    """Render typed reports into deterministic local artifacts."""

    JSON_NAME = "production-research-report.json"
    MARKDOWN_NAME = "production-research-report.md"

    def export(
        self,
        report: ProviderResearchReport,
        output_directory: Path,
    ) -> tuple[Path, Path]:
        """Write one JSON and one Markdown report to an explicit directory."""

        output_directory.mkdir(parents=True, exist_ok=True)
        json_path = output_directory / self.JSON_NAME
        markdown_path = output_directory / self.MARKDOWN_NAME
        json_path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        return json_path, markdown_path

    @staticmethod
    def to_markdown(report: ProviderResearchReport) -> str:
        """Render a readable report without provider-generated content."""

        lines = [
            f"# {report.department_name}",
            "",
            report.data_notice,
            "",
            "## Methodology",
            "",
            report.methodology,
            "",
            "## Category summary",
            "",
            "| Category | Providers | Approved | Average | Recommendation |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
        for category in report.categories:
            lines.append(
                f"| {category.category.value.replace('_', ' ').title()} | "
                f"{category.provider_count} | {category.approved_count} | "
                f"{category.average_score:.2f} | "
                f"{category.recommended_provider or 'None'} |"
            )
        lines.extend(["", "## Provider evaluations", ""])
        for provider in report.providers:
            lines.extend(
                [
                    f"### {provider.name}",
                    "",
                    f"- Category: {provider.category.value}",
                    f"- Status: {provider.status.value}",
                    f"- Local score: {provider.local_score}/100",
                    f"- Website: {provider.website}",
                    f"- Free tier recorded: {provider.free_tier_available}",
                    f"- Trial recorded: {provider.trial_available}",
                    f"- API recorded: {provider.api_available}",
                    f"- Pricing model: {provider.pricing_model.value}",
                    f"- Last reviewed: {provider.last_reviewed.isoformat()}",
                    f"- Recommended use: {provider.recommended_use_case}",
                    f"- Commercial notes: {provider.commercial_license_notes}",
                    f"- Strengths: {'; '.join(provider.strengths)}",
                    f"- Weaknesses: {'; '.join(provider.weaknesses)}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"
