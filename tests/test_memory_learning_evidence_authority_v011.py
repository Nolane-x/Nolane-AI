from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.learning_authority import LearningEvidenceAuthority


def _evidence(
    evidence_id: str = "evidence-clean",
    verifier: str = "verification.chief",
    *,
    passed: bool = True,
    false_accepts: int = 0,
    regressions: int = 0,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id,
        verifier,
        passed,
        false_accepts=false_accepts,
        regressions=regressions,
        notes="subject-bound learning verification",
    )


def _subject_digest(*, subject_id: str = "skill-alpha", revision: int = 1) -> str:
    return canonical_digest({"subject_id": subject_id, "revision": revision})


def _issue(authority: LearningEvidenceAuthority, **overrides):
    values = {
        "subject_kind": "skill",
        "subject_id": "skill-alpha",
        "operation_class": "skill.verify",
        "producer_agent_id": "coding.worker",
        "evidence": _evidence(),
        "subject_digest": _subject_digest(),
        "single_use": True,
        "event_anchor_id": "event-0001",
    }
    values.update(overrides)
    return authority.issue(**values)


def test_exact_binding_is_content_addressed_and_duplicate_issue_does_not_mint_fresh_capability() -> None:
    authority = LearningEvidenceAuthority()
    first = _issue(authority)
    second = _issue(authority)

    assert second is first
    assert first.sequence == 1
    assert first.lease_id.startswith("learning-evidence-")
    assert first.subject_kind == "skill"
    assert first.subject_id == "skill-alpha"
    assert first.operation_class == "skill.verify"
    assert first.producer_agent_id == "coding.worker"
    assert first.verifier_agent_id == "verification.chief"
    assert first.evidence_id == "evidence-clean"
    assert first.evidence_digest == canonical_digest(_evidence().to_state())
    assert first.subject_digest == _subject_digest()
    assert first.single_use is True
    assert authority.to_state()["lease_counter"] == 1


def test_positive_authority_requires_clean_independent_verifier() -> None:
    authority = LearningEvidenceAuthority()
    with pytest.raises(PermissionError, match="independent verifier"):
        _issue(authority, evidence=_evidence(verifier="coding.worker"))

    for evidence in (
        _evidence(passed=False),
        _evidence(false_accepts=1),
        _evidence(regressions=1),
    ):
        with pytest.raises(PermissionError, match="clean evidence"):
            _issue(authority, evidence=evidence)


def test_require_fails_closed_on_subject_operation_state_or_evidence_laundering() -> None:
    authority = LearningEvidenceAuthority()
    lease = _issue(authority)

    authority.require(
        lease.lease_id,
        subject_kind="skill",
        subject_id="skill-alpha",
        operation_class="skill.verify",
        producer_agent_id="coding.worker",
        evidence=_evidence(),
        subject_digest=_subject_digest(),
    )

    mismatches = (
        {"subject_id": "skill-beta"},
        {"operation_class": "self_model.update_competence"},
        {"producer_agent_id": "coding.other"},
        {"subject_digest": _subject_digest(revision=2)},
        {"evidence": _evidence(evidence_id="evidence-other")},
    )
    baseline = {
        "subject_kind": "skill",
        "subject_id": "skill-alpha",
        "operation_class": "skill.verify",
        "producer_agent_id": "coding.worker",
        "evidence": _evidence(),
        "subject_digest": _subject_digest(),
    }
    for override in mismatches:
        values = dict(baseline)
        values.update(override)
        with pytest.raises(PermissionError, match="does not authorize exact learning operation"):
            authority.require(lease.lease_id, **values)


def test_same_evidence_id_with_rebound_evidence_body_is_rejected() -> None:
    authority = LearningEvidenceAuthority()
    lease = _issue(authority)
    rebound = EvidenceRecord(
        "evidence-clean",
        "verification.chief",
        True,
        false_accepts=0,
        regressions=0,
        notes="different evidence body under the same id",
    )

    with pytest.raises(PermissionError, match="exact learning operation"):
        authority.require(
            lease.lease_id,
            subject_kind="skill",
            subject_id="skill-alpha",
            operation_class="skill.verify",
            producer_agent_id="coding.worker",
            evidence=rebound,
            subject_digest=_subject_digest(),
        )


def test_single_use_lease_is_consumed_once_and_replay_is_denied() -> None:
    authority = LearningEvidenceAuthority()
    lease = _issue(authority)
    values = {
        "subject_kind": "skill",
        "subject_id": "skill-alpha",
        "operation_class": "skill.verify",
        "producer_agent_id": "coding.worker",
        "evidence": _evidence(),
        "subject_digest": _subject_digest(),
        "use_ref": "skill-verification-receipt-1",
    }
    receipt = authority.consume(lease.lease_id, **values)

    assert receipt.sequence == 1
    assert receipt.lease_id == lease.lease_id
    assert receipt.use_ref == "skill-verification-receipt-1"
    assert authority.to_state()["use_counter"] == 1
    with pytest.raises(PermissionError, match="already consumed"):
        authority.consume(lease.lease_id, **values)


def test_unconsumed_lease_survives_restore_but_does_not_create_a_use_receipt() -> None:
    authority = LearningEvidenceAuthority()
    lease = _issue(authority)
    restored = LearningEvidenceAuthority.from_state(authority.to_state())

    assert restored.lease(lease.lease_id) == lease
    assert restored.uses_for(lease.lease_id) == ()
    assert restored.to_state() == authority.to_state()


def test_restore_rejects_rehashed_semantic_laundering_and_gapful_ledgers() -> None:
    authority = LearningEvidenceAuthority()
    lease = _issue(authority)
    state = authority.to_state()

    forged = deepcopy(state)
    forged_lease = forged["leases"][0]
    forged_lease["subject_id"] = "skill-beta"
    forged_lease["subject_digest"] = _subject_digest(subject_id="skill-beta")
    forged_lease["digest"] = canonical_digest({key: value for key, value in forged_lease.items() if key != "digest"})
    with pytest.raises(ValueError, match="lease id|canonical binding"):
        LearningEvidenceAuthority.from_state(forged)

    gapful = deepcopy(state)
    gapful["lease_counter"] = 2
    with pytest.raises(ValueError, match="gapless|counter"):
        LearningEvidenceAuthority.from_state(gapful)


def test_restore_rejects_single_use_receipt_rebinding_even_when_receipt_is_rehashed() -> None:
    authority = LearningEvidenceAuthority()
    lease = _issue(authority)
    authority.consume(
        lease.lease_id,
        subject_kind="skill",
        subject_id="skill-alpha",
        operation_class="skill.verify",
        producer_agent_id="coding.worker",
        evidence=_evidence(),
        subject_digest=_subject_digest(),
        use_ref="skill-verification-receipt-1",
    )
    state = authority.to_state()
    forged = deepcopy(state)
    forged_use = forged["uses"][0]
    forged_use["subject_id"] = "skill-beta"
    forged_use["digest"] = canonical_digest({key: value for key, value in forged_use.items() if key != "digest"})

    with pytest.raises(ValueError, match="lease binding|exact lease"):
        LearningEvidenceAuthority.from_state(forged)
