"""Controlled Mission Zero revision and export regression coverage."""

import json
from pathlib import Path

import pytest

from company_missions.first_real_content.dashboard import (
    create_sample_first_content_input,
)
from company_missions.first_real_content.exporter import FirstContentMissionExporter
from company_missions.first_real_content.models import (
    FirstContentMissionInput,
    FirstContentMissionResult,
)
from company_missions.first_real_content.review import (
    FirstContentFounderReviewService,
)
from company_missions.first_real_content.runner import (
    FirstRealContentMissionRunner,
)
from core import ApprovalStatus, ValidationError
from creative_quality.models import QualityDepartment, QualityDimension
from creative_quality.scoring import CreativeQualityScorer
from mission_engine import MissionArtifactType, MissionExecutionStatus
from production.models import ProductionApprovalStatus, RenderStatus


@pytest.fixture(scope="module")
def revision_run() -> tuple[
    FirstRealContentMissionRunner,
    FirstContentMissionInput,
    FirstContentMissionResult,
    FirstContentMissionResult,
]:
    value = create_sample_first_content_input().model_copy(
        update={
            "mission_title": "AuraAI Mission Zero",
            "topic": "I built an AI media company with specialized AI roles",
            "preferred_keywords": ["AuraAI", "AI agents"],
            "target_duration_seconds": 600,
            "founder_quality_threshold": 80,
            "sample_data": False,
        }
    )
    runner = FirstRealContentMissionRunner()
    original = runner.run_typed(value)
    revised = FirstContentFounderReviewService(
        runner
    ).request_and_execute_content_revision(
        original,
        value,
        "Improve Hook, Story, Retention, and Subtitles without changing evidence.",
    )
    return runner, value, original, revised


def test_one_revision_succeeds_and_second_is_rejected(
    revision_run,
) -> None:
    runner, _, _, revised = revision_run

    assert revised.revision_request is not None
    assert revised.pilot.quality_artifact.revision_count == 1
    with pytest.raises(ValidationError) as caught:
        FirstContentFounderReviewService(runner).request_content_revision(
            revised,
            "Do another revision.",
        )
    assert caught.value.error_code == "PILOT_REVISION_LIMIT_REACHED"


def test_script_and_package_versions_preserve_lineage(revision_run) -> None:
    _, _, original, revised = revision_run
    script_v1, script_v2 = revised.script_versions

    assert script_v1 == original.script_versions[0]
    assert script_v1.version_number == 1
    assert script_v2.version_number == 2
    assert script_v2.parent_artifact_id == script_v1.artifact_id
    assert revised.production_versions[0] == original.production_package
    assert revised.quality_versions[0] == original.creative_quality_package
    assert revised.pilot.research_artifact == original.pilot.research_artifact
    assert revised.pilot.seo_artifact == original.pilot.seo_artifact


def test_revised_quality_improves_only_targeted_weak_departments(
    revision_run,
) -> None:
    _, _, original, revised = revision_run
    comparison = revised.quality_comparison

    assert comparison is not None
    assert comparison.original_overall_score == (
        original.creative_quality_package.scores.overall
    )
    assert comparison.revised_overall_score == (
        revised.creative_quality_package.scores.overall
    )
    changes = {item.department: item.change for item in comparison.departments}
    for department in (
        QualityDepartment.HOOK,
        QualityDepartment.STORY,
        QualityDepartment.RETENTION,
        QualityDepartment.SUBTITLES,
    ):
        assert changes[department] > 0
    for department in (
        QualityDepartment.MOTION,
        QualityDepartment.THUMBNAIL,
        QualityDepartment.FACTUALITY,
    ):
        assert changes[department] == 0
    assert comparison.revised_blocker_count == 0
    assert revised.creative_quality_package.gate.founder_override_used is False


def test_revised_subtitles_preserve_words_timing_and_readability(
    revision_run,
) -> None:
    _, _, _, revised = revision_run
    package = revised.production_package
    analyses = revised.creative_quality_package.subtitle_optimization.lines

    assert all(item.characters_per_line <= 42 for item in analyses)
    assert all(item.line_count <= 2 for item in analyses)
    assert all(item.reading_speed_cps <= 20 for item in analyses)
    assert all(
        len(line) <= 42
        for segment in package.subtitle_package.segments
        for line in segment.text.splitlines()
    )
    narration_words = " ".join(
        segment.text for segment in package.voiceover_plan.segments
    ).split()
    subtitle_words = " ".join(
        segment.text.replace("\n", " ")
        for segment in package.subtitle_package.segments
    ).split()
    assert subtitle_words == narration_words
    assert package.subtitle_package.segments[-1].end_seconds == pytest.approx(
        package.voiceover_plan.total_duration_seconds,
        abs=0.01,
    )


def test_revision_remains_at_founder_review_without_delivery(revision_run) -> None:
    _, _, _, revised = revision_run

    assert revised.mission.status == MissionExecutionStatus.FOUNDER_REVIEW
    assert revised.mission.founder_approval_state == ApprovalStatus.PENDING
    assert revised.production_package.approval_status == ProductionApprovalStatus.PENDING
    assert revised.production_package.assembly_manifest.render_status == (
        RenderStatus.NOT_RENDERED
    )
    assert revised.production_review.rendered is False
    assert revised.production_review.published is False
    assert revised.founder_review.rendered is False
    assert revised.founder_review.published is False


def test_revision_artifacts_and_history_are_registered(revision_run) -> None:
    _, _, _, revised = revision_run
    artifacts = revised.mission.produced_artifacts

    assert {item.artifact_type for item in artifacts} >= {
        MissionArtifactType.SCRIPT,
        MissionArtifactType.PRODUCTION_PACKAGE,
        MissionArtifactType.QUALITY_REPORT,
        MissionArtifactType.REVISION_REQUEST,
        MissionArtifactType.APPROVAL_NOTES,
    }
    assert any(
        item.action == "founder_revision_requested"
        for item in revised.mission.history
    )
    assert any(
        item.action == "controlled_revision_completed"
        for item in revised.mission.history
    )


def test_revision_export_contains_comparison_and_both_versions(
    revision_run,
    tmp_path: Path,
) -> None:
    _, _, _, revised = revision_run
    target, _ = FirstContentMissionExporter(tmp_path).export(revised)
    required = (
        "script/script-v1.json",
        "script/script-v2.json",
        "quality/original/quality-breakdown.json",
        "quality/revised/quality-breakdown.json",
        "production/original/production-package.json",
        "production/revised/production-package.json",
        "revision/revision-request.json",
        "revision/score-comparison.json",
        "mission/artifact-version-history.json",
        "founder-review/review-summary.md",
    )

    assert all((target / path).is_file() for path in required)
    comparison = json.loads(
        (target / "revision/score-comparison.json").read_text(encoding="utf-8")
    )
    assert comparison["revised_overall_score"] > comparison[
        "original_overall_score"
    ]
    review = (target / "founder-review/review-summary.md").read_text(
        encoding="utf-8"
    )
    assert "../revision/score-comparison.md" in review
    assert "NOT RENDERED" in review
    assert "NOT PUBLISHED" in review


def test_scoring_and_provider_boundaries_remain_unchanged(revision_run) -> None:
    runner, _, _, revised = revision_run
    values = {dimension: 80 for dimension in QualityDimension}

    assert CreativeQualityScorer().calculate(values).overall == 80
    assert runner.pilot.provider_router is None
    assert revised.provider_usage.live_enabled is False
    assert revised.provider_usage.total_requests == 0
