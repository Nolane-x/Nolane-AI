from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.fabric import MemoryScope, MemoryStatus
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind


class _RegistryStub:
    def __init__(self) -> None:
        self._actors = {
            "memory.chief": SimpleNamespace(agent_id="memory.chief", region="memory-context-knowledge"),
            "memory.worker": SimpleNamespace(agent_id="memory.worker", region="memory-context-knowledge"),
            "verification.chief": SimpleNamespace(agent_id="verification.chief", region="truth-knowledge"),
            "verification.second": SimpleNamespace(agent_id="verification.second", region="truth-knowledge"),
        }

    def get(self, agent_id: str):
        return self._actors[str(agent_id)]


class _EventStub:
    def latest_event_id(self):
        return None

    def get(self, event_id: str):
        raise KeyError(event_id)


def _substrate() -> LearningSubstrate:
    return LearningSubstrate(registry=_RegistryStub(), events=_EventStub())


def _evidence(evidence_id: str, verifier: str = "verification.chief") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id,
        verifier,
        True,
        false_accepts=0,
        regressions=0,
        notes="v0.0.12 exact-state memory authority",
    )


def _candidate(substrate: LearningSubstrate, *, text: str = "verified-looking memory"):
    return substrate.remember(
        text=text,
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("caller-string-is-not-authority",),
        confidence=0.99,
    )


def _admit(substrate: LearningSubstrate, row, *, evidence_id: str = "memory-admission-proof"):
    evidence = _evidence(evidence_id)
    digest = substrate.memory_verification_subject_digest(row.memory_id)
    lease = substrate.learning_authority.issue(
        subject_kind="memory",
        subject_id=row.memory_id,
        operation_class="memory.verify",
        producer_agent_id=row.owner_agent_id,
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )
    admitted = substrate.validate_memory(
        row.memory_id,
        actor_agent_id="memory.worker",
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    return admitted, evidence, lease


def _forget_lease(
    substrate: LearningSubstrate,
    row,
    *,
    reason: str = "privacy retention expired",
    evidence_id: str = "forget-proof",
):
    evidence = _evidence(evidence_id)
    digest = substrate.forget_subject_digest(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason=reason,
    )
    lease = substrate.learning_authority.issue(
        subject_kind="memory",
        subject_id=row.memory_id,
        operation_class="memory.forget",
        producer_agent_id="memory.worker",
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )
    return evidence, lease


def test_caller_string_evidence_cannot_create_active_verified_memory() -> None:
    substrate = _substrate()
    row = _candidate(substrate)

    assert row.status is MemoryStatus.QUARANTINED
    assert substrate.metadata(row.memory_id).epistemic_type is not EpistemicType.VERIFIED

    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-09-01T00:00:00+00:00",
    )
    assert bundle.selected == ()
    assert dict(bundle.rejected)[row.memory_id] == MemoryStatus.QUARANTINED.value


def test_memory_admission_requires_actual_clean_subject_bound_evidence() -> None:
    substrate = _substrate()
    row = _candidate(substrate)
    evidence = _evidence("admission-proof")

    with pytest.raises(PermissionError, match="preissued|lease|authority"):
        substrate.validate_memory(
            row.memory_id,
            actor_agent_id="memory.worker",
            evidence=evidence,
        )
    assert substrate.memory.get(row.memory_id).status is MemoryStatus.QUARANTINED

    admitted, _, lease = _admit(substrate, row, evidence_id="admission-proof")
    assert admitted.status is MemoryStatus.ACTIVE
    assert substrate.metadata(row.memory_id).epistemic_type is EpistemicType.VERIFIED
    uses = substrate.learning_authority.uses_for(lease.lease_id)
    assert len(uses) == 1
    assert uses[0].operation_class == "memory.verify"
    assert uses[0].subject_id == row.memory_id
    lifecycle = substrate.lifecycle.receipts_for(row.memory_id)[-1]
    assert lifecycle.new_status is MemoryStatus.ACTIVE
    assert lifecycle.correction_ref == uses[0].receipt_id


def test_memory_admission_rejects_stale_and_cross_memory_leases() -> None:
    substrate = _substrate()
    first = _candidate(substrate, text="candidate one")
    second = _candidate(substrate, text="candidate two")
    evidence = _evidence("admission-proof")
    lease = substrate.learning_authority.issue(
        subject_kind="memory",
        subject_id=first.memory_id,
        operation_class="memory.verify",
        producer_agent_id=first.owner_agent_id,
        evidence=evidence,
        subject_digest=substrate.memory_verification_subject_digest(first.memory_id),
        single_use=True,
    )

    with pytest.raises(PermissionError, match="exact learning operation|authorize"):
        substrate.validate_memory(
            second.memory_id,
            actor_agent_id="memory.worker",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )

    substrate.lifecycle.transition(
        first.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.CONTRADICTED,
        reason="new contradictory observation",
        evidence_refs=("contradiction-proof",),
    )
    with pytest.raises(PermissionError, match="exact learning operation|authorize"):
        substrate.validate_memory(
            first.memory_id,
            actor_agent_id="memory.worker",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )
    assert substrate.memory.get(first.memory_id).status is MemoryStatus.CONTRADICTED


def test_first_time_forgetting_requires_preissued_exact_state_authority() -> None:
    substrate = _substrate()
    row = _candidate(substrate)
    _admit(substrate, row)
    evidence = _evidence("forget-proof")

    with pytest.raises(PermissionError, match="preissued|lease|authority"):
        substrate.forget(
            row.memory_id,
            actor_agent_id="memory.worker",
            reason="privacy retention expired",
            evidence=evidence,
        )
    assert substrate.memory.get(row.memory_id).status is MemoryStatus.ACTIVE
    with pytest.raises(KeyError):
        substrate.tombstone(row.memory_id)


def test_forget_lease_binds_memory_actor_reason_and_current_state_before_archive() -> None:
    substrate = _substrate()
    row = _candidate(substrate)
    _admit(substrate, row)
    evidence, lease = _forget_lease(substrate, row)

    with pytest.raises(PermissionError, match="exact learning operation|authorize"):
        substrate.forget(
            row.memory_id,
            actor_agent_id="memory.worker",
            reason="different reason",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )
    assert substrate.memory.get(row.memory_id).status is MemoryStatus.ACTIVE

    tombstone = substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="privacy retention expired",
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    assert substrate.memory.get(row.memory_id).status is MemoryStatus.ARCHIVED
    assert tombstone.authorization_use_receipt_id
    forget = substrate.to_state()["forget_receipts"][0]
    assert forget["authorization_use_receipt_id"] == tombstone.authorization_use_receipt_id
    uses = substrate.learning_authority.uses_for(lease.lease_id)
    assert len(uses) == 1
    assert uses[0].receipt_id == tombstone.authorization_use_receipt_id
    assert uses[0].operation_class == "memory.forget"


def test_forget_authorization_replay_and_cross_memory_use_fail_closed() -> None:
    substrate = _substrate()
    first = _candidate(substrate, text="first admitted memory")
    second = _candidate(substrate, text="second admitted memory")
    _admit(substrate, first, evidence_id="admit-first")
    _admit(substrate, second, evidence_id="admit-second")
    evidence, lease = _forget_lease(substrate, first)

    with pytest.raises(PermissionError, match="exact learning operation|authorize"):
        substrate.forget(
            second.memory_id,
            actor_agent_id="memory.worker",
            reason="privacy retention expired",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )
    assert substrate.memory.get(second.memory_id).status is MemoryStatus.ACTIVE

    substrate.forget(
        first.memory_id,
        actor_agent_id="memory.worker",
        reason="privacy retention expired",
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    with pytest.raises(PermissionError, match="already consumed|lease"):
        substrate.learning_authority.consume(
            lease.lease_id,
            subject_kind="memory",
            subject_id=first.memory_id,
            operation_class="memory.forget",
            producer_agent_id="memory.worker",
            evidence=evidence,
            subject_digest=substrate.forget_subject_digest(
                first.memory_id,
                actor_agent_id="memory.worker",
                reason="privacy retention expired",
            ),
            use_ref="forged-replay",
        )


def test_restore_rejects_forged_forget_authority_linkage() -> None:
    substrate = _substrate()
    row = _candidate(substrate)
    _admit(substrate, row)
    evidence, lease = _forget_lease(substrate, row)
    substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="privacy retention expired",
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )

    state = substrate.to_state()
    authority_state = substrate.learning_authority.to_state()
    forged = deepcopy(state)
    forged["forget_receipts"][0]["authorization_use_receipt_id"] = "learning-evidence-use-99999999"
    forged["forget_receipts"][0]["digest"] = "forged"

    with pytest.raises(ValueError, match="digest|authorization|authority"):
        LearningSubstrate.from_state(
            registry=_RegistryStub(),
            events=_EventStub(),
            state=forged,
            learning_authority=substrate.learning_authority.from_state(authority_state),
        )
