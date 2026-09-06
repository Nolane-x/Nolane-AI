from __future__ import annotations

import pytest

from nolane.external_core.integration_admission_bundle import (
    AdmissionAuditFinding,
    CanonicalAdmissionAuditReport,
)


def test_clean_current_v4_report_requires_exact_observation_digest() -> None:
    with pytest.raises(ValueError, match="clean current.*observation digest"):
        CanonicalAdmissionAuditReport.create(
            (),
            current_observation=True,
            observation_digest=None,
        )


@pytest.mark.parametrize("bad_digest", ["", "   ", True, 7, object()])
def test_current_v4_report_rejects_non_exact_observation_digest(
    bad_digest: object,
) -> None:
    with pytest.raises(ValueError, match="observation digest"):
        CanonicalAdmissionAuditReport.create(
            (
                AdmissionAuditFinding(
                    code="TEST_FINDING",
                    detail="test-only finding",
                    subject_id="test",
                ),
            ),
            current_observation=True,
            observation_digest=bad_digest,  # type: ignore[arg-type]
        )


def test_failed_current_v4_report_may_represent_unavailable_witness() -> None:
    report = CanonicalAdmissionAuditReport.create(
        (
            AdmissionAuditFinding(
                code="CURRENT_OBSERVATION_WITNESS_UNAVAILABLE",
                detail="current observation audit requires an explicit canonical observation witness",
                subject_id="canonical-observation",
            ),
        ),
        current_observation=True,
        observation_digest=None,
    )

    assert report.protocol == "external-integration-admission-audit-v4"
    assert report.observation_digest is None
    assert report.findings
