from company_missions.local_render_pilot import create_review_ready_production_package
from distribution.publishing_plan import PublishingPreparationService
from production.creator_package import CreatorPackageService


def test_publishing_preparation_supports_three_platforms_but_stays_disabled():
    creator = CreatorPackageService().build(create_review_ready_production_package())
    manifest = PublishingPreparationService().build(creator)
    assert manifest == PublishingPreparationService().build(creator)
    assert [item.channel.value for item in manifest.plans] == ["youtube", "instagram", "tiktok"]
    assert len(manifest.content_hash) == 64
    assert manifest.founder_approval_required
    assert not manifest.publishing_enabled and not manifest.uploaded and not manifest.published
    assert all(not item.schedule.automatic_scheduling for item in manifest.plans)
    assert all(not item.retry.automatic_retry for item in manifest.plans)
