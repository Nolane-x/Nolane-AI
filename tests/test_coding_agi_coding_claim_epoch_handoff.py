import copy

import pytest

from cogcoder.organization.code_claims import (
    COMPONENT_VERSION,
    ClaimMode,
    ClaimStatus,
    CodeClaimHandoffReceipt,
    CodeClaimLease,
    CodeClaimLedger,
)


def _bound_claim(
    ledger: CodeClaimLedger,
    *,
    agent: str = "coding.backend.01",
    task: str = "T-1",
    revision: str = "rev-a",
    operation_ref: str = "claim-op-auth",
):
    claim = ledger.claim(
        agent_id=agent,
        task_id=task,
        file_paths=("src/api/auth.py",),
        symbol_ids=("AuthService.refresh",),
        mode=ClaimMode.EXCLUSIVE_WRITE,
        source_revision=revision,
        operation_ref=operation_ref,
    )
    return claim, ledger.lease(claim.claim_id)


def test_same_agent_cannot_hold_overlapping_exclusive_claims_for_different_tasks():
    ledger = CodeClaimLedger()
    ledger.claim(
        agent_id="coding.backend.01",
        task_id="T-1",
        file_paths=("src/api/auth.py",),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    before = ledger.to_state()

    with pytest.raises(PermissionError):
        ledger.claim(
            agent_id="coding.backend.01",
            task_id="T-2",
            file_paths=("src/api/auth.py",),
            mode=ClaimMode.EXCLUSIVE_WRITE,
        )

    assert ledger.to_state() == before


def test_bound_claim_operation_ref_is_idempotent_and_cannot_be_rebound():
    ledger = CodeClaimLedger()
    first, first_lease = _bound_claim(ledger)
    before = ledger.to_state()

    second = ledger.claim(
        agent_id="coding.backend.01",
        task_id="T-1",
        file_paths=("src/api/auth.py",),
        symbol_ids=("AuthService.refresh",),
        mode=ClaimMode.EXCLUSIVE_WRITE,
        source_revision="rev-a",
        operation_ref="claim-op-auth",
    )
    assert second == first
    assert ledger.lease(second.claim_id) == first_lease
    assert ledger.to_state() == before

    with pytest.raises(ValueError, match="operation_ref"):
        ledger.claim(
            agent_id="coding.backend.01",
            task_id="T-1",
            file_paths=("src/api/other.py",),
            mode=ClaimMode.EXCLUSIVE_WRITE,
            source_revision="rev-a",
            operation_ref="claim-op-auth",
        )
    assert ledger.to_state() == before


def test_bound_claim_requires_complete_revision_and_operation_binding():
    ledger = CodeClaimLedger()
    with pytest.raises(ValueError):
        ledger.claim(
            agent_id="coding.backend.01",
            task_id="T-1",
            file_paths=("src/api/auth.py",),
            source_revision="rev-a",
        )
    with pytest.raises(ValueError):
        ledger.claim(
            agent_id="coding.backend.01",
            task_id="T-1",
            file_paths=("src/api/auth.py",),
            operation_ref="claim-op-auth",
        )


def test_current_coverage_requires_matching_revision_and_epoch():
    ledger = CodeClaimLedger()
    claim, lease = _bound_claim(ledger)

    assert isinstance(lease, CodeClaimLease)
    assert lease.claim_id == claim.claim_id
    assert lease.operation_ref == "claim-op-auth"
    assert lease.source_revision == "rev-a"
    assert lease.epoch > 0
    assert lease.authority == "coordination_only"

    assert ledger.covers_current(
        agent_id="coding.backend.01",
        task_id="T-1",
        file_paths=("src/api/auth.py",),
        symbol_ids=("AuthService.refresh",),
        current_source_revision="rev-a",
        min_claim_epoch=lease.epoch,
    )
    assert not ledger.covers_current(
        agent_id="coding.backend.01",
        task_id="T-1",
        file_paths=("src/api/auth.py",),
        symbol_ids=("AuthService.refresh",),
        current_source_revision="rev-b",
        min_claim_epoch=lease.epoch,
    )
    assert not ledger.covers_current(
        agent_id="coding.backend.01",
        task_id="T-1",
        file_paths=("src/api/auth.py",),
        symbol_ids=("AuthService.refresh",),
        current_source_revision="rev-a",
        min_claim_epoch=lease.epoch + 1,
    )


def test_atomic_handoff_supersedes_old_claim_and_transfers_exact_scope():
    ledger = CodeClaimLedger()
    old, old_lease = _bound_claim(ledger)

    receipt = ledger.handoff(
        old.claim_id,
        actor_agent_id="coding.backend.01",
        new_agent_id="coding.systems.01",
        new_task_id="T-2",
        new_source_revision="rev-b",
        operation_ref="handoff-op-auth",
        expected_epoch=old_lease.epoch,
    )

    assert isinstance(receipt, CodeClaimHandoffReceipt)
    assert receipt.old_claim_id == old.claim_id
    assert receipt.authority == "coordination_only"
    assert ledger.get(old.claim_id).status is ClaimStatus.SUPERSEDED

    new = ledger.get(receipt.new_claim_id)
    new_lease = ledger.lease(new.claim_id)
    assert new.status is ClaimStatus.ACTIVE
    assert new.agent_id == "coding.systems.01"
    assert new.task_id == "T-2"
    assert new.file_paths == old.file_paths
    assert new.symbol_ids == old.symbol_ids
    assert new.directory_prefixes == old.directory_prefixes
    assert new.mode is old.mode
    assert new_lease.source_revision == "rev-b"
    assert new_lease.epoch > old_lease.epoch
    assert receipt.old_epoch == old_lease.epoch
    assert receipt.new_epoch == new_lease.epoch

    assert not ledger.covers_current(
        agent_id="coding.backend.01",
        task_id="T-1",
        file_paths=old.file_paths,
        symbol_ids=old.symbol_ids,
        current_source_revision="rev-a",
        min_claim_epoch=old_lease.epoch,
    )
    assert ledger.covers_current(
        agent_id="coding.systems.01",
        task_id="T-2",
        file_paths=new.file_paths,
        symbol_ids=new.symbol_ids,
        current_source_revision="rev-b",
        min_claim_epoch=new_lease.epoch,
    )

    before_retry = ledger.to_state()
    same = ledger.handoff(
        old.claim_id,
        actor_agent_id="coding.backend.01",
        new_agent_id="coding.systems.01",
        new_task_id="T-2",
        new_source_revision="rev-b",
        operation_ref="handoff-op-auth",
        expected_epoch=old_lease.epoch,
    )
    assert same == receipt
    assert ledger.to_state() == before_retry


def test_stale_epoch_handoff_is_failure_atomic():
    ledger = CodeClaimLedger()
    old, old_lease = _bound_claim(ledger)
    before = ledger.to_state()

    with pytest.raises(ValueError, match="epoch"):
        ledger.handoff(
            old.claim_id,
            actor_agent_id="coding.backend.01",
            new_agent_id="coding.systems.01",
            new_task_id="T-2",
            new_source_revision="rev-b",
            operation_ref="handoff-op-auth",
            expected_epoch=old_lease.epoch + 1,
        )

    assert ledger.to_state() == before


def test_bound_state_round_trip_and_legacy_state_restore():
    ledger = CodeClaimLedger()
    old, old_lease = _bound_claim(ledger)
    receipt = ledger.handoff(
        old.claim_id,
        actor_agent_id="coding.chief",
        new_agent_id="coding.systems.01",
        new_task_id="T-2",
        new_source_revision="rev-b",
        operation_ref="handoff-op-auth",
        expected_epoch=old_lease.epoch,
    )
    restored = CodeClaimLedger.from_state(ledger.to_state())
    assert restored.to_state() == ledger.to_state()
    assert restored.handoffs() == (receipt,)

    legacy = CodeClaimLedger()
    legacy_claim = legacy.claim(
        agent_id="coding.backend.01",
        task_id="LEGACY",
        file_paths=("src/legacy.py",),
    )
    old_state = {
        "counter": legacy.to_state()["counter"],
        "claims": legacy.to_state()["claims"],
    }
    lifted = CodeClaimLedger.from_state(old_state)
    assert lifted.get(legacy_claim.claim_id) == legacy_claim
    assert lifted.covers(
        agent_id="coding.backend.01",
        task_id="LEGACY",
        file_paths=("src/legacy.py",),
        symbol_ids=(),
    )
    with pytest.raises(KeyError):
        lifted.lease(legacy_claim.claim_id)


def test_restore_rejects_operation_ref_rebinding_and_cross_task_overlap():
    ledger = CodeClaimLedger()
    first, _ = _bound_claim(ledger)
    ledger.release(first.claim_id, actor_agent_id="coding.backend.01")
    second = ledger.claim(
        agent_id="coding.systems.01",
        task_id="T-2",
        file_paths=("src/runtime/loop.py",),
        source_revision="rev-b",
        operation_ref="claim-op-runtime",
    )
    state = ledger.to_state()

    rebound = copy.deepcopy(state)
    rebound["leases"][1]["operation_ref"] = rebound["leases"][0]["operation_ref"]
    with pytest.raises(ValueError, match="operation_ref"):
        CodeClaimLedger.from_state(rebound)

    conflicting = copy.deepcopy(state)
    conflicting["claims"][0]["status"] = ClaimStatus.ACTIVE.value
    conflicting["claims"][1]["agent_id"] = "coding.backend.01"
    conflicting["claims"][1]["file_paths"] = ["src/api/auth.py"]
    with pytest.raises(ValueError, match="conflicting active exclusive"):
        CodeClaimLedger.from_state(conflicting)

    assert ledger.get(second.claim_id).status is ClaimStatus.ACTIVE


def test_restore_rejects_epoch_counter_inflation_without_recorded_lease():
    ledger = CodeClaimLedger()
    _bound_claim(ledger)
    state = copy.deepcopy(ledger.to_state())
    state["epoch_counter"] += 100

    with pytest.raises(ValueError, match="epoch"):
        CodeClaimLedger.from_state(state)


def test_component_version_advances_for_epoch_handoff_protocol():
    assert COMPONENT_VERSION == "0.0.2"
