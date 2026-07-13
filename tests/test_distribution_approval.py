import pytest

from distribution.approval import DistributionApprovalService
from distribution.models import PublishingState
from tests.distribution_helpers import distribution_package


def test_founder_approval_flow_requires_every_manual_confirmation() -> None:
    package = distribution_package()
    service = DistributionApprovalService()

    with pytest.raises(ValueError):
        service.approve(
            package,
            founder_name="Founder",
            approval_note="Incomplete review.",
            confirmed_checklist_keys=set(),
        )

    keys = {item.key for item in package.manual_approval_checklist.items}
    approved = service.approve(
        package,
        founder_name="Founder",
        approval_note="All manual checks complete.",
        confirmed_checklist_keys=keys,
    )
    ready = service.mark_ready_to_upload(approved)
    uploaded = service.confirm_manual_upload(ready, founder_confirmed=True)

    assert approved.publication_status == PublishingState.FOUNDER_APPROVED
    assert ready.publication_status == PublishingState.READY_TO_UPLOAD
    assert uploaded.publication_status == PublishingState.UPLOADED_MANUALLY
    assert uploaded.automatic_publishing is False
    assert all(item.completed for item in uploaded.publish_checklist)


def test_approval_states_cannot_be_skipped_or_automated() -> None:
    package = distribution_package()
    service = DistributionApprovalService()

    with pytest.raises(ValueError):
        service.mark_ready_to_upload(package)
    with pytest.raises(ValueError):
        service.confirm_manual_upload(package, founder_confirmed=False)
