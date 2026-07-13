import pytest

from company_missions import create_review_ready_production_package
from creative_quality.models import CreativeQualityPackage
from creative_quality.pipeline import create_creative_quality_pipeline
from creative_quality.revision_engine import DeterministicRevisionEngine


def test_revision_preserves_original_and_applies_safe_copy_changes() -> None:
    package = create_review_ready_production_package()
    result = create_creative_quality_pipeline().run(package)
    quality = CreativeQualityPackage.model_validate(
        result.data["creative_quality_package"]
    )
    original_hook = package.script.hook
    original_sources = [list(item.source_notes) for item in package.script.sections]
    revised, plan, applied = DeterministicRevisionEngine().revise(package, quality)
    assert package.script.hook == original_hook
    assert revised is not package
    assert revised.script.hook == quality.hook_analysis.improved_hook
    assert [item.source_notes for item in revised.script.sections] == original_sources
    assert (
        revised.thumbnail_plan.recommended_concept_id
        == quality.thumbnail_report.recommended_concept_id
    )
    assert plan.actions == [] or plan.actions[0].instruction
    assert applied


def test_revision_count_is_bounded() -> None:
    engine = DeterministicRevisionEngine(maximum_revision_count=1)
    with pytest.raises(ValueError):
        engine.create_plan([], revision_count=1)
