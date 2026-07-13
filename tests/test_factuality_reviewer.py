from agents.specialists import FactualityReviewer
from company_missions import create_review_ready_production_package
from core import TaskRecord
from creative_quality.models import FactualityReport, QualitySeverity


def test_income_guarantee_without_evidence_is_blocking() -> None:
    package = create_review_ready_production_package().model_copy(deep=True)
    section = package.script.sections[0].model_copy(
        update={
            "claims_requiring_verification": [
                "This method guarantees instant income of $1000."
            ],
            "source_notes": [],
        }
    )
    package.script.sections[0] = section
    employee = FactualityReviewer()
    task = TaskRecord(
        title="Review claims", input_data={"production_package": package}
    )
    employee.accept_task(task)
    result = employee.execute_current_task()
    report = FactualityReport.model_validate(result.data["factuality_report"])
    assert report.passed is False
    assert report.high_risk_claim_count == 1
    assert report.claims[0].risk_level == QualitySeverity.BLOCKING
    assert report.prohibited_claims_found
    employee.clear_current_task()
