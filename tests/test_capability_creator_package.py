from company_missions.local_render_pilot import create_review_ready_production_package
from production.creator_package import CreatorPackageService


def test_creator_package_reuses_complete_production_outputs_without_rendering():
    source = create_review_ready_production_package()
    first = CreatorPackageService().build(source)
    second = CreatorPackageService().build(source)
    assert first == second
    assert first.final_script == source.script
    assert first.narration_package == source.voiceover_plan
    assert first.scene_breakdown == source.storyboard
    assert len(first.metadata.title_options) == 3
    assert not first.rendering_performed and not first.upload_performed and not first.publishing_performed
