from company_missions import create_review_ready_production_package
from creative_quality.models import (
    CreativeQualityPackage,
    QualityGateStatus,
)
from creative_quality.pipeline import create_creative_quality_pipeline
from production.rendering.pipeline import LocalRenderPipeline


def quality_package() -> tuple:
    production = create_review_ready_production_package()
    result = create_creative_quality_pipeline().run(production)
    quality = CreativeQualityPackage.model_validate(
        result.data["creative_quality_package"]
    )
    return production, quality


def test_passed_quality_permits_separate_founder_render_flow() -> None:
    production, quality = quality_package()
    assert quality.gate.status == QualityGateStatus.PASSED
    assert LocalRenderPipeline._validate_quality_gate(
        production,
        quality,
        enforcement_enabled=True,
        founder_quality_override=False,
    ) is None
    assert quality.gate.status == QualityGateStatus.PASSED


def test_blocked_quality_stops_render_and_legacy_flow_stays_available() -> None:
    production, quality = quality_package()
    blocker = quality.model_copy(
        update={
            "gate": quality.gate.model_copy(
                update={
                    "status": QualityGateStatus.BLOCKED,
                    "blocking_issues": [
                        quality.issues[0].model_copy(update={"blocking": True})
                    ] if quality.issues else [],
                    "founder_override_allowed": False,
                    "founder_override_used": False,
                }
            )
        }
    )
    failure = LocalRenderPipeline._validate_quality_gate(
        production,
        blocker,
        enforcement_enabled=True,
        founder_quality_override=False,
    )
    assert failure is not None
    assert failure.error_code == "CREATIVE_QUALITY_BLOCKED"
    assert LocalRenderPipeline._validate_quality_gate(
        production,
        None,
        enforcement_enabled=False,
        founder_quality_override=False,
    ) is None
