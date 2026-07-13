"""Heuristic retention-risk analysis without audience prediction claims."""

from __future__ import annotations

from creative_quality.models import (
    QualitySeverity,
    RetentionReport,
    RetentionRisk,
)
from production.models import VideoScript


class RetentionEngine:
    """Locate deterministic pacing and repetition risks by timestamp."""

    def analyze(self, script: VideoScript) -> RetentionReport:
        risks: list[RetentionRisk] = []
        timestamp = 0.0
        devices: set[str] = set()
        for section in script.sections:
            duration = section.estimated_duration_seconds
            words_per_minute = len(section.narration.split()) / duration * 60
            repeated_device = section.retention_device.lower() in devices
            devices.add(section.retention_device.lower())
            if duration > 65:
                risks.append(
                    self._risk(
                        timestamp + min(duration * 0.65, duration),
                        section.section_id,
                        QualitySeverity.MEDIUM,
                        "long_section",
                        "A long uninterrupted section may create fatigue.",
                        "The viewer may feel progress has stalled.",
                        "Add a concise recap, contrast, or visual pattern interrupt.",
                    )
                )
            if words_per_minute > 180:
                risks.append(
                    self._risk(
                        timestamp,
                        section.section_id,
                        QualitySeverity.HIGH,
                        "information_density",
                        "The spoken information density is high.",
                        "The viewer may miss a key step or disengage.",
                        "Split the idea and add a comprehension pause.",
                    )
                )
            if repeated_device:
                risks.append(
                    self._risk(
                        timestamp,
                        section.section_id,
                        QualitySeverity.LOW,
                        "repetition",
                        "The same retention device is repeated.",
                        "The structure may begin to feel predictable.",
                        "Use a different question, example, or visual contrast.",
                    )
                )
            timestamp += duration
        generic_hook = script.hook.lower().startswith(
            ("in this video", "today we", "welcome")
        )
        if generic_hook:
            risks.insert(
                0,
                self._risk(
                    0,
                    script.sections[0].section_id,
                    QualitySeverity.HIGH,
                    "early_drop_off",
                    "The opening delays a viewer-specific reason to continue.",
                    "The viewer may leave before the core value is clear.",
                    "Open with the problem, credible contrast, and useful promise.",
                ),
            )
        penalties = sum(
            {
                QualitySeverity.LOW: 3,
                QualitySeverity.MEDIUM: 7,
                QualitySeverity.HIGH: 12,
                QualitySeverity.BLOCKING: 20,
                QualitySeverity.INFO: 1,
            }[risk.severity]
            for risk in risks
        )
        average = max(45.0, 88.0 - penalties)
        duration = script.total_estimated_duration_seconds
        return RetentionReport(
            script_id=script.script_id,
            production_duration_seconds=duration,
            estimated_average_retention_score=average,
            first_30_seconds_score=62 if generic_hook else 86,
            middle_retention_score=max(50, average - 2),
            ending_retention_score=min(92, average + 4),
            risks=risks,
            pattern_interrupt_recommendations=[
                "Change visual framing after each major idea.",
                "Use a concrete example before adding another abstraction.",
            ],
            curiosity_loop_recommendations=[
                "Open one evidence question early and resolve it before the CTA."
            ],
            engagement_prompts=[
                "Invite viewers to compare the workflow with their current process."
            ],
            call_to_action_timing=round(min(duration * 0.88, duration), 2),
        )

    @staticmethod
    def _risk(
        timestamp: float,
        section_id,
        severity: QualitySeverity,
        risk_type: str,
        explanation: str,
        response: str,
        remediation: str,
    ) -> RetentionRisk:
        return RetentionRisk(
            timestamp_seconds=round(timestamp, 2),
            section_id=section_id,
            severity=severity,
            risk_type=risk_type,
            explanation=explanation,
            likely_viewer_response=response,
            remediation=remediation,
        )
