"""Explicit founder-controlled manual publishing transitions."""

from __future__ import annotations

from core import DepartmentName, utc_now
from distribution.models import (
    ApprovalChange,
    DistributionPackage,
    ManualApprovalChecklist,
    PublishChecklistItem,
    PublishingState,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventType
from runtime_engine.state_manager import RuntimeStateManager


class DistributionApprovalService:
    """Apply only valid manual state changes; never publish content."""

    def __init__(
        self,
        *,
        state_manager: RuntimeStateManager | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.state_manager = state_manager
        self.event_bus = event_bus or (
            state_manager.event_bus if state_manager is not None else None
        )

    def approve(
        self,
        package: DistributionPackage,
        *,
        founder_name: str,
        approval_note: str,
        confirmed_checklist_keys: set[str],
    ) -> DistributionPackage:
        """Record explicit founder approval after all checks are confirmed."""

        if package.publication_status != PublishingState.READY_FOR_REVIEW:
            raise ValueError("Only a review-ready package can be approved.")
        checklist = package.manual_approval_checklist.model_copy(deep=True)
        checklist.items = [
            item.model_copy(
                update={
                    "completed": item.completed or item.key in confirmed_checklist_keys
                }
            )
            for item in checklist.items
        ]
        if not checklist.complete:
            raise ValueError("Every required manual approval item must be confirmed.")
        checklist.founder_name = founder_name
        checklist.approval_note = approval_note
        checklist.approved_at = utc_now()
        publish_checklist = [
            item.model_copy(
                update={
                    "completed": item.completed or item.key in confirmed_checklist_keys
                }
            )
            for item in package.publish_checklist
        ]
        return self._transition(
            package,
            PublishingState.FOUNDER_APPROVED,
            "Founder explicitly approved the reviewed local package.",
            checklist=checklist,
            publish_checklist=publish_checklist,
        )

    def mark_ready_to_upload(
        self,
        package: DistributionPackage,
    ) -> DistributionPackage:
        """Mark a founder-approved package ready for a manual upload."""

        if package.publication_status != PublishingState.FOUNDER_APPROVED:
            raise ValueError("Founder approval is required before upload readiness.")
        return self._transition(
            package,
            PublishingState.READY_TO_UPLOAD,
            "Local upload instructions are ready for founder execution.",
        )

    def confirm_manual_upload(
        self,
        package: DistributionPackage,
        *,
        founder_confirmed: bool,
    ) -> DistributionPackage:
        """Record a founder-reported upload; never execute one."""

        if not founder_confirmed:
            raise ValueError("Explicit manual upload confirmation is required.")
        if package.publication_status != PublishingState.READY_TO_UPLOAD:
            raise ValueError("Package is not ready for manual upload.")
        return self._transition(
            package,
            PublishingState.UPLOADED_MANUALLY,
            "Founder confirmed an upload performed outside AuraAI.",
        )

    def mark_metrics_imported(
        self,
        package: DistributionPackage,
    ) -> DistributionPackage:
        """Record completion of a manual metrics import."""

        if package.publication_status != PublishingState.UPLOADED_MANUALLY:
            raise ValueError("Metrics require a founder-confirmed manual upload.")
        return self._transition(
            package,
            PublishingState.METRICS_IMPORTED,
            "Founder-supplied metrics were imported locally.",
        )

    def _transition(
        self,
        package: DistributionPackage,
        state: PublishingState,
        reason: str,
        *,
        checklist: ManualApprovalChecklist | None = None,
        publish_checklist: list[PublishChecklistItem] | None = None,
    ) -> DistributionPackage:
        history = [
            *package.approval_history,
            ApprovalChange(
                previous_state=package.publication_status,
                new_state=state,
                reason=reason,
            ),
        ]
        updated = package.model_copy(
            update={
                "publication_status": state,
                "approval_history": history,
                "manual_approval_checklist": (
                    checklist or package.manual_approval_checklist
                ),
                "publish_checklist": (
                    publish_checklist or package.publish_checklist
                ),
            }
        )
        if self.state_manager is not None:
            self.state_manager.register_distribution_package(
                updated,
                replace=True,
            )
        if self.event_bus is not None:
            self.event_bus.emit(
                RuntimeEventType.APPROVAL_CHANGED,
                reason,
                department=DepartmentName.DISTRIBUTION,
                metadata={
                    "previous_state": package.publication_status.value,
                    "new_state": state.value,
                    "automatic_publishing": False,
                },
            )
        return updated
