"""Founder approval recording with independent content and render gates."""

from __future__ import annotations

from core import ValidationError
from mission_engine import MissionArtifactType, MissionManager

from private_video_production.models import (
    PrivateVideoApproval,
    PrivateVideoProductionInput,
)


class PrivateVideoApprovalService:
    """Create and verify content-bound founder approvals."""

    def record(
        self,
        production_input: PrivateVideoProductionInput,
        *,
        content_approved: bool,
        private_render_approved: bool,
        founder_confirmed: bool,
        founder_notes: str = "",
    ) -> PrivateVideoApproval:
        """Record explicit approvals; command presence is insufficient."""

        if not founder_confirmed:
            raise ValidationError(
                "Explicit founder confirmation is required.",
                error_code="FOUNDER_CONFIRMATION_REQUIRED",
            )
        return PrivateVideoApproval(
            mission_id=production_input.mission_id,
            script_artifact_id=production_input.script_artifact_id,
            script_version=production_input.script_version,
            content_approved=content_approved,
            private_render_approved=private_render_approved,
            publishing_approved=False,
            founder_notes=founder_notes,
            content_hash=production_input.script_content_hash,
        )

    @staticmethod
    def register_artifact(
        manager: MissionManager,
        approval: PrivateVideoApproval,
    ):
        """Register approval metadata through the existing MissionManager."""

        return manager.register_artifact(
            approval.mission_id,
            artifact_type=MissionArtifactType.APPROVAL_NOTES,
            name="PrivateVideoApproval",
            summary=(
                "Founder-controlled private video approval boundaries recorded; "
                f"content={approval.content_approved}, "
                f"private_render={approval.private_render_approved}, publishing=false."
            ),
            producer="Founder",
            founder_review_required=True,
            metadata_reference=f"private-video-approval:{approval.approval_id}",
            metadata={
                "approval_id": str(approval.approval_id),
                "script_artifact_id": str(approval.script_artifact_id),
                "script_version": approval.script_version,
                "content_hash": approval.content_hash,
                "content_approved": approval.content_approved,
                "private_render_approved": approval.private_render_approved,
                "publishing_approved": False,
            },
        )

    @staticmethod
    def require_content(
        approval: PrivateVideoApproval | None,
        production_input: PrivateVideoProductionInput,
    ) -> None:
        """Require approval bound to the exact revised script."""

        if approval is None or not approval.content_approved:
            raise ValidationError(
                "Content approval is required.",
                error_code="CONTENT_APPROVAL_REQUIRED",
            )
        PrivateVideoApprovalService._verify_binding(approval, production_input)

    @staticmethod
    def require_private_render(
        approval: PrivateVideoApproval | None,
        production_input: PrivateVideoProductionInput,
    ) -> None:
        """Require both exact content and private-render approval."""

        PrivateVideoApprovalService.require_content(approval, production_input)
        if approval is None or not approval.private_render_approved:
            raise ValidationError(
                "Private render approval is required.",
                error_code="PRIVATE_RENDER_APPROVAL_REQUIRED",
            )

    @staticmethod
    def _verify_binding(
        approval: PrivateVideoApproval,
        production_input: PrivateVideoProductionInput,
    ) -> None:
        if (
            approval.mission_id != production_input.mission_id
            or approval.script_artifact_id != production_input.script_artifact_id
            or approval.script_version != production_input.script_version
            or approval.content_hash != production_input.script_content_hash
        ):
            raise ValidationError(
                "Approval does not match the loaded content.",
                error_code="APPROVAL_CONTENT_MISMATCH",
            )
