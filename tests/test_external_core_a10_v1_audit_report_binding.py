from __future__ import annotations

import pytest

from nolane.external_core.integration_admission_bundle import (
    AdmissionAuditFinding,
    CanonicalAdmissionAuditReport,
)


VALID_OBSERVATION_DIGEST = "canonical-observation-v1-" + ("0" * 64)


def _finding() -> AdmissionAuditFinding:
    return AdmissionAuditFinding(
        code="TEST_FINDING",
        detail="test-only finding",
        subject_id="test",
    )


def test_clean_current_v4_report_requires_exact_observation_digest() -> None:
    with pytest.raises(ValueError, match="clean current.*observation digest"):
        CanonicalAdmissionAuditReport.create(
            (),
            current_observation=True,
            observation_digest=None,
        )


@pytest.mark.parametrize("bad_digest", ["", "   ", True, 7, object()])
def test_current_v4_report_rejects_non_exact_observation_digest_type(
    bad_digest: object,
) -> None:
    with pytest.raises(ValueError, match="observation digest"):
        CanonicalAdmissionAuditReport.create(
            (_finding(),),
            current_observation=True,
            observation_digest=bad_digest,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "bad_digest",
    [
        "not-an-observation-digest",
        "canonical-observation-v1-",
        "canonical-observation-v1-" + ("0" * 63),
        "canonical-observation-v1-" + ("0" * 65),
        "canonical-observation-v1-" + ("g" * 64),
        "canonical-observation-v1-" + ("A" * 64),
        "other-observation-v1-" + ("0" * 64),
    ],
)
def test_current_v4_report_rejects_wrong_observation_digest_identity(
    bad_digest: str,
) -> None:
    with pytest.raises(ValueError, match="observation digest"):
        CanonicalAdmissionAuditReport.create(
            (_finding(),),
            current_observation=True,
            observation_digest=bad_digest,
        )


def test_current_v4_report_accepts_exact_observation_digest_identity() -> None:
    report = CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest=VALID_OBSERVATION_DIGEST,
    )

    assert report.protocol == "external-integration-admission-audit-v4"
    assert report.observation_digest == VALID_OBSERVATION_DIGEST


@pytest.mark.parametrize("bad_current_mode", [None, 0, 1, "true", object()])
def test_audit_report_rejects_non_boolean_current_mode(bad_current_mode: object) -> None:
    with pytest.raises(ValueError, match="current_observation"):
        CanonicalAdmissionAuditReport.create(
            (_finding(),),
            current_observation=bad_current_mode,  # type: ignore[arg-type]
            observation_digest=VALID_OBSERVATION_DIGEST,
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
