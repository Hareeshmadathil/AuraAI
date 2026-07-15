"""Founder-facing explanations for deterministic Creative Quality results."""

from __future__ import annotations

from creative_quality.models import (
    CreativeQualityIssue,
    CreativeQualityPackage,
    QualityBreakdown,
    QualityDepartment,
    QualityDepartmentBreakdown,
    QualityDimension,
    QualityRecommendation,
    QualitySeverity,
)


class CreativeQualityIntelligence:
    """Derive an auditable report without changing any quality score."""

    def build(self, quality: CreativeQualityPackage) -> QualityBreakdown:
        """Build the seven-department founder decision report."""

        departments = [
            self._department_report(quality, department, dimensions, employee)
            for department, dimensions, employee in self._department_configuration()
        ]
        blockers = self._sorted_blockers(quality)
        strengths = [
            f"{item.department.value.title()} scored {item.score:.2f} and met "
            "its review threshold."
            for item in sorted(
                (report for report in departments if report.passed),
                key=lambda report: report.score,
                reverse=True,
            )
        ]
        weaknesses = [
            f"{item.department.value.title()} scored {item.score:.2f}, below the "
            f"{quality.gate.minimum_required_score:.2f} review threshold."
            for item in departments
            if not item.passed
        ]
        recommendations = self._overall_recommendations(departments)
        estimated_gain = self._estimated_gain(quality, departments)
        return QualityBreakdown(
            executive_summary=self._executive_summary(quality, departments),
            overall_score=quality.scores.overall,
            gate_status=quality.gate.status,
            departments=departments,
            blocking_issues=blockers,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            estimated_improvement_points=estimated_gain,
            estimated_score_after_revision=round(
                min(100.0, quality.scores.overall + estimated_gain),
                2,
            ),
        )

    def _department_report(
        self,
        quality: CreativeQualityPackage,
        department: QualityDepartment,
        dimensions: tuple[QualityDimension, ...],
        employee: str,
    ) -> QualityDepartmentBreakdown:
        weight = sum(quality.score_weights[dimension] for dimension in dimensions)
        contribution = sum(
            getattr(quality.scores, dimension.value)
            * quality.score_weights[dimension]
            for dimension in dimensions
        )
        score = round(contribution / weight, 2)
        issues = [
            issue for issue in quality.issues if issue.dimension in dimensions
        ]
        blockers = self._sort_issues(
            [issue for issue in issues if issue.blocking]
        )
        warnings = [
            f"{issue.title}: {issue.description}"
            for issue in self._sort_issues(
                [issue for issue in issues if not issue.blocking]
            )
        ]
        recommendations = self._department_recommendations(
            quality,
            department,
            issues,
        )
        return QualityDepartmentBreakdown(
            department=department,
            score=score,
            weight=round(weight, 4),
            passed=score >= quality.gate.minimum_required_score and not blockers,
            contributing_dimensions=list(dimensions),
            blockers=blockers,
            warnings=warnings,
            recommendations=recommendations,
            suggested_employee=employee,
        )

    @staticmethod
    def _department_configuration() -> tuple[
        tuple[QualityDepartment, tuple[QualityDimension, ...], str], ...
    ]:
        return (
            (
                QualityDepartment.HOOK,
                (QualityDimension.HOOK,),
                "Hook Architect",
            ),
            (
                QualityDepartment.STORY,
                (QualityDimension.STORY, QualityDimension.CLARITY),
                "Story Director",
            ),
            (
                QualityDepartment.RETENTION,
                (
                    QualityDimension.PACING,
                    QualityDimension.RETENTION,
                    QualityDimension.CALL_TO_ACTION,
                ),
                "Retention Auditor",
            ),
            (
                QualityDepartment.MOTION,
                (
                    QualityDimension.MOTION,
                    QualityDimension.PRODUCTION_COMPLETENESS,
                ),
                "Motion Designer",
            ),
            (
                QualityDepartment.SUBTITLES,
                (QualityDimension.SUBTITLES,),
                "Subtitle Designer",
            ),
            (
                QualityDepartment.THUMBNAIL,
                (QualityDimension.THUMBNAIL,),
                "Thumbnail Psychologist",
            ),
            (
                QualityDepartment.FACTUALITY,
                (QualityDimension.FACTUALITY, QualityDimension.TRUST),
                "Factuality Reviewer",
            ),
        )

    def _department_recommendations(
        self,
        quality: CreativeQualityPackage,
        department: QualityDepartment,
        issues: list[CreativeQualityIssue],
    ) -> list[str]:
        issue_actions = [
            issue.remediation
            for issue in self._sort_issues(issues)
            if issue.remediation
        ]
        report_actions = {
            QualityDepartment.HOOK: quality.hook_analysis.recommendations,
            QualityDepartment.STORY: [
                *quality.story_report.recommendations,
                *[
                    improvement
                    for section in quality.story_report.sections
                    for improvement in section.improvements
                ],
            ],
            QualityDepartment.RETENTION: [
                *quality.retention_report.pattern_interrupt_recommendations,
                *quality.retention_report.curiosity_loop_recommendations,
                *quality.retention_report.engagement_prompts,
                *[risk.remediation for risk in quality.retention_report.risks],
            ],
            QualityDepartment.MOTION: [
                "Keep motion cues restrained and preserve reading time."
            ],
            QualityDepartment.SUBTITLES: [
                "Keep every subtitle line within 42 characters and review cues "
                "with more than two mobile-readable lines."
            ],
            QualityDepartment.THUMBNAIL: [
                *[
                    recommendation
                    for concept in quality.thumbnail_report.concepts
                    for recommendation in concept.recommendations
                ],
                quality.thumbnail_report.recommendation_reason,
            ],
            QualityDepartment.FACTUALITY: [
                *[
                    claim.remediation
                    for claim in quality.factuality_report.claims
                    if claim.verification_required or not claim.evidence_supplied
                ],
                *quality.factuality_report.disclaimer_requirements,
            ],
        }[department]
        defaults = {
            QualityDepartment.HOOK: (
                "Preserve a truthful, specific opening promise."
            ),
            QualityDepartment.STORY: (
                "Preserve clear narrative progression and transitions."
            ),
            QualityDepartment.RETENTION: (
                "Review pacing and curiosity loops before render."
            ),
            QualityDepartment.MOTION: "Preserve accessible, purpose-led visual movement.",
            QualityDepartment.SUBTITLES: "Review mobile readability before render.",
            QualityDepartment.THUMBNAIL: "Use the highest-scoring truthful concept.",
            QualityDepartment.FACTUALITY: (
                "Verify marked claims against supplied evidence."
            ),
        }
        return self._unique([*issue_actions, *report_actions, defaults[department]])

    @staticmethod
    def _overall_recommendations(
        departments: list[QualityDepartmentBreakdown],
    ) -> list[QualityRecommendation]:
        recommendations: list[QualityRecommendation] = []
        for report in departments:
            priority = (
                QualitySeverity.HIGH
                if report.blockers
                else QualitySeverity.MEDIUM
                if not report.passed or report.warnings
                else QualitySeverity.LOW
            )
            recommendations.append(
                QualityRecommendation(
                    department=report.department,
                    recommendation=report.recommendations[0],
                    suggested_employee=report.suggested_employee,
                    priority=priority,
                )
            )
        priority_order = {
            QualitySeverity.BLOCKING: 4,
            QualitySeverity.HIGH: 3,
            QualitySeverity.MEDIUM: 2,
            QualitySeverity.LOW: 1,
            QualitySeverity.INFO: 0,
        }
        return sorted(
            recommendations,
            key=lambda item: priority_order[item.priority],
            reverse=True,
        )

    @staticmethod
    def _estimated_gain(
        quality: CreativeQualityPackage,
        departments: list[QualityDepartmentBreakdown],
    ) -> float:
        planned_gain = quality.revision_plan.estimated_quality_gain
        if planned_gain > 0:
            return round(min(100.0 - quality.scores.overall, planned_gain), 2)
        actionable = sum(
            bool(report.blockers or report.warnings or not report.passed)
            for report in departments
        )
        return round(
            min(100.0 - quality.scores.overall, actionable * 2.5),
            2,
        )

    @staticmethod
    def _executive_summary(
        quality: CreativeQualityPackage,
        departments: list[QualityDepartmentBreakdown],
    ) -> str:
        passed = sum(report.passed for report in departments)
        return (
            f"The unchanged Creative Quality heuristic scored this package "
            f"{quality.scores.overall:.2f}/100. {passed} of {len(departments)} "
            f"founder-facing departments met the "
            f"{quality.gate.minimum_required_score:.2f} review threshold. "
            f"The current gate is {quality.gate.status.value.replace('_', ' ')}."
        )

    def _sorted_blockers(
        self,
        quality: CreativeQualityPackage,
    ) -> list[CreativeQualityIssue]:
        by_id = {
            issue.issue_id: issue
            for issue in [*quality.issues, *quality.gate.blocking_issues]
            if issue.blocking
        }
        return self._sort_issues(list(by_id.values()))

    @staticmethod
    def _sort_issues(
        issues: list[CreativeQualityIssue],
    ) -> list[CreativeQualityIssue]:
        order = {
            QualitySeverity.BLOCKING: 4,
            QualitySeverity.HIGH: 3,
            QualitySeverity.MEDIUM: 2,
            QualitySeverity.LOW: 1,
            QualitySeverity.INFO: 0,
        }
        return sorted(
            issues,
            key=lambda issue: (-order[issue.severity], issue.title.lower()),
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def render_quality_breakdown_markdown(breakdown: QualityBreakdown) -> str:
    """Render one safe, readable founder report as Markdown."""

    rows = [
        "| Department | Score | Weight | Result | Suggested employee |",
        "| --- | ---: | ---: | --- | --- |",
        *[
            f"| {item.department.value.title()} | {item.score:.2f} | "
            f"{item.weight * 100:.1f}% | "
            f"{'Pass' if item.passed else 'Fail'} | "
            f"{item.suggested_employee} |"
            for item in breakdown.departments
        ],
    ]
    sections = [
        "# Creative Quality Intelligence V2",
        "",
        "## Executive Summary",
        "",
        breakdown.executive_summary,
        "",
        "## Overall Score",
        "",
        f"**{breakdown.overall_score:.2f} / 100**",
        "",
        f"Gate: **{breakdown.gate_status.value}**",
        "",
        "## Department Table",
        "",
        *rows,
        "",
        "## Blocking Issues",
        "",
        *_markdown_issues(breakdown.blocking_issues),
        "",
        "## Strengths",
        "",
        *_markdown_items(breakdown.strengths, "No strengths were reported."),
        "",
        "## Weaknesses",
        "",
        *_markdown_items(
            breakdown.weaknesses,
            "No threshold weaknesses were reported.",
        ),
        "",
        "## Recommendations",
        "",
        *[
            f"- **{item.priority.value.title()} — "
            f"{item.suggested_employee}:** {item.recommendation}"
            for item in breakdown.recommendations
        ],
        "",
        "## Estimated improvement after revision",
        "",
        "Estimated heuristic improvement: "
        f"**+{breakdown.estimated_improvement_points:.2f} points** "
        f"to **{breakdown.estimated_score_after_revision:.2f}/100**.",
        "",
        breakdown.heuristic_notice,
        "",
        "## Department Details",
        "",
    ]
    for department in breakdown.departments:
        sections.extend(
            [
                f"### {department.department.value.title()}",
                "",
                f"Suggested employee: **{department.suggested_employee}**",
                "",
                "Warnings:",
                *_markdown_items(department.warnings, "No warnings."),
                "",
                "Recommendations:",
                *_markdown_items(department.recommendations, "No recommendations."),
                "",
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def _markdown_issues(issues: list[CreativeQualityIssue]) -> list[str]:
    if not issues:
        return ["- No blocking issues."]
    return [
        f"- **{issue.severity.value.title()} — {issue.title}:** "
        f"{issue.description} Remediation: {issue.remediation}"
        for issue in issues
    ]


def _markdown_items(values: list[str], empty_message: str) -> list[str]:
    return [f"- {value}" for value in values] or [f"- {empty_message}"]
