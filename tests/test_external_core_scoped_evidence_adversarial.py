from __future__ import annotations

import pytest

from nolane.external_core.evidence import ScopedEvidenceRecord


def _kwargs() -> dict[str, object]:
    return {
        "evidence_id": "scoped-ev-adv",
        "subject_id": "external.integration",
        "subject_version": "0.0.3",
        "subject_digest": "subject-digest",
        "scope_digest": "scope-digest",
        "verifier_agent_id": "verification.agent.adv",
        "observed_epoch": 3,
        "passed": True,
        "false_accepts": 0,
        "regressions": 0,
        "evidence_refs": ("ev:source",),
        "limitations": (),
    }


def test_adversarial_scoped_evidence_rejects_non_string_identity_smuggling() -> None:
    for field in ("evidence_id", "subject_id", "subject_version", "subject_digest", "scope_digest", "verifier_agent_id"):
        values = _kwargs()
        values[field] = 7
        with pytest.raises(ValueError):
            ScopedEvidenceRecord.create(**values)  # type: ignore[arg-type]


def test_adversarial_scoped_evidence_rejects_boolean_numeric_smuggling() -> None:
    for field in ("observed_epoch", "false_accepts", "regressions"):
        values = _kwargs()
        values[field] = True
        with pytest.raises(ValueError):
            ScopedEvidenceRecord.create(**values)  # type: ignore[arg-type]


def test_adversarial_scoped_evidence_requires_exact_boolean_passed() -> None:
    for bad in (1, 0, "true", "false"):
        values = _kwargs()
        values["passed"] = bad
        with pytest.raises(ValueError):
            ScopedEvidenceRecord.create(**values)  # type: ignore[arg-type]


def test_adversarial_scoped_evidence_rejects_negative_epoch_or_counters() -> None:
    for field in ("observed_epoch", "false_accepts", "regressions"):
        values = _kwargs()
        values[field] = -1
        with pytest.raises(ValueError):
            ScopedEvidenceRecord.create(**values)  # type: ignore[arg-type]


def test_adversarial_scoped_evidence_requires_non_empty_provenance() -> None:
    values = _kwargs()
    values["evidence_refs"] = ()
    with pytest.raises(ValueError, match="evidence refs|provenance"):
        ScopedEvidenceRecord.create(**values)  # type: ignore[arg-type]


def test_adversarial_direct_constructor_forgery_fails_integrity_validation() -> None:
    valid = ScopedEvidenceRecord.create(**_kwargs())  # type: ignore[arg-type]
    forged = ScopedEvidenceRecord(
        evidence_id=valid.evidence_id,
        subject_id=valid.subject_id,
        subject_version=valid.subject_version,
        subject_digest=valid.subject_digest,
        scope_digest=valid.scope_digest,
        verifier_agent_id=valid.verifier_agent_id,
        observed_epoch=valid.observed_epoch,
        passed=valid.passed,
        false_accepts=valid.false_accepts,
        regressions=valid.regressions,
        evidence_refs=valid.evidence_refs,
        limitations=valid.limitations,
        digest="forged",
    )
    with pytest.raises(ValueError, match="integrity"):
        forged.validate_integrity()


def test_adversarial_duplicate_set_like_refs_are_rejected() -> None:
    values = _kwargs()
    values["evidence_refs"] = ("ev:source", "ev:source")
    with pytest.raises(ValueError, match="duplicate"):
        ScopedEvidenceRecord.create(**values)  # type: ignore[arg-type]
