from copy import deepcopy

import pytest

from nolane.external_core.goal_design import CoherenceError
from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    LEGACY_UNATTESTED_TRUST,
    mint_verified_goal_integrity_evolution_receipt,
)
from nolane.external_core.goal_design_integrity_evolution_authority import (
    GOAL_INTEGRITY_EVOLUTION_ACTION,
    GoalIntegrityEvolutionAuthorityVerifier,
)
from nolane.external_core.goal_design_integrity_runtime import (
    LEGACY_UNVERIFIED_AUTHORITY_TRUST,
    VERIFIED_CAPABILITY_AUTHORITY_TRUST,
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)
from nolane.external_core.goal_design_revision_history import (
    ROOT_INTEGRITY_CONTRACT_TRUST,
    GoalRevisionHistoryCompiler,
    verify_goal_revision_history_export,
)

_AUTHORITY_KEY = b"revision-history-authority-key-32"
_GOAL_ID = "goal:revision-history"


class _Clock:
    def __init__(self, value: int = 100) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


def _contract(
    statement: str,
    *,
    goal_id: str = _GOAL_ID,
) -> GoalIntegrityContract:
    return GoalIntegrityContract(
        goal_id=goal_id,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                goal_id,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:reviewed-user-intent",
            ),
            GoalIntegrityClause(
                "constraint:user-control",
                goal_id,
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Preserve explicit user control.",
                "prov:user-control",
            ),
        ),
    )


def _verifier():
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=_Clock(),
    )
    grant = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=(_GOAL_ID,),
        actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s=50,
        valid_until_epoch_s=500,
    )
    return verifier, grant


def _blank_runtime(verifier) -> GoalIntegrityRuntime:
    runtime = GoalIntegrityRuntime.__new__(GoalIntegrityRuntime)
    runtime.integrity_authority = GoalIntegrityAuthorityIndex()
    runtime._integrity_contracts = {}
    runtime._current_contracts = {}
    runtime._contract_predecessors = {}
    runtime._evolution_receipts = {}
    runtime._legacy_unattested_evolution_digests = set()
    runtime._legacy_unverified_authority_digests = set()
    runtime._verified_capability_evolution_digests = set()
    runtime.evolution_authority_verifier = verifier
    return runtime


def _verified_receipt(verifier, grant, predecessor, successor, tag: str):
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=predecessor,
        successor=successor,
    )
    return mint_verified_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authorization_proof=proof,
        reason=f"Reviewed Goal/Design revision {tag} for public history projection.",
        source_refs=(f"source:{tag}",),
        evidence_refs=(f"evidence:{tag}",),
        freshness_ref=f"freshness:{tag}",
        confidence_milli=940,
    )


def _verified_revision_runtime():
    verifier, grant = _verifier()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve the reviewed revised terminal intent.")
    receipt = _verified_receipt(verifier, grant, original, revised, "revision-100")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )
    return runtime, original, revised, receipt


def _compile_from_runtime(runtime, *, current_digest=None, contracts=None, predecessors=None, receipts=None, trust=None):
    return GoalRevisionHistoryCompiler().compile(
        goal_id=_GOAL_ID,
        current_contract_digest=current_digest or runtime._current_contracts[_GOAL_ID],
        contracts=contracts or dict(runtime._integrity_contracts),
        predecessors=predecessors or dict(runtime._contract_predecessors),
        evolution_receipts=(
            dict(runtime._evolution_receipts) if receipts is None else receipts
        ),
        trust_label_resolver=trust or runtime.evolution_trust_label,
    )


def test_runtime_exports_typed_verified_goal_revision_history():
    runtime, original, revised, receipt = _verified_revision_runtime()

    history = runtime.goal_revision_history(original.goal_id)

    assert history.snapshot.current_contract_digest == revised.digest
    assert tuple(entry.contract_digest for entry in history.snapshot.entries) == (
        original.digest,
        revised.digest,
    )
    assert history.snapshot.entries[1].evolution_receipt_id == receipt.receipt_id
    assert history.snapshot.entries[1].source_refs == receipt.source_refs
    assert history.snapshot.entries[1].evidence_refs == receipt.evidence_refs
    assert history.snapshot.entries[1].freshness_ref == receipt.freshness_ref
    assert history.snapshot.entries[1].confidence_milli == receipt.confidence_milli
    assert history.snapshot.entries[1].trust_label == VERIFIED_CAPABILITY_AUTHORITY_TRUST
    assert verify_goal_revision_history_export(history) == history.snapshot


def test_root_only_history_is_truthful_deterministic_and_does_not_invent_freshness():
    runtime = _blank_runtime(None)
    root = _contract("Preserve the root terminal intent.")
    runtime.install_integrity_contract(root)

    first = runtime.goal_revision_history(root.goal_id)
    second = runtime.goal_revision_history(root.goal_id)
    entry = first.snapshot.entries[0]

    assert entry.ordinal == 0
    assert entry.trust_label == ROOT_INTEGRITY_CONTRACT_TRUST
    assert entry.evolution_receipt_id is None
    assert entry.delta_digest is None
    assert entry.evidence_refs == ()
    assert entry.freshness_ref is None
    assert entry.confidence_milli is None
    assert set(entry.source_refs) == {
        "prov:reviewed-user-intent",
        "prov:user-control",
    }
    assert first.snapshot.history_digest == second.snapshot.history_digest
    assert first.receipt.receipt_id == second.receipt.receipt_id


def test_history_capability_negotiation_is_fail_closed():
    runtime, original, _, _ = _verified_revision_runtime()

    with pytest.raises(CoherenceError, match="protocol major"):
        runtime.goal_revision_history(original.goal_id, protocol_major=2)
    with pytest.raises(CoherenceError, match="minimum minor"):
        runtime.goal_revision_history(original.goal_id, minimum_minor=1)

    accepted = runtime.goal_revision_history(
        original.goal_id,
        protocol_major=1,
        minimum_minor=0,
    )
    assert accepted.snapshot.capability.major == 1
    assert accepted.snapshot.capability.minor == 0


def test_mapping_insertion_order_cannot_change_history_identity():
    runtime, original, _, _ = _verified_revision_runtime()
    baseline = runtime.goal_revision_history(original.goal_id)

    contracts = dict(reversed(tuple(runtime._integrity_contracts.items())))
    predecessors = dict(reversed(tuple(runtime._contract_predecessors.items())))
    receipts = dict(reversed(tuple(runtime._evolution_receipts.items())))
    reordered = _compile_from_runtime(
        runtime,
        contracts=contracts,
        predecessors=predecessors,
        receipts=receipts,
    )

    assert tuple(entry.entry_digest for entry in reordered.snapshot.entries) == tuple(
        entry.entry_digest for entry in baseline.snapshot.entries
    )
    assert reordered.snapshot.history_digest == baseline.snapshot.history_digest
    assert reordered.receipt.receipt_id == baseline.receipt.receipt_id


def test_multi_revision_history_is_topology_ordered_and_hash_chained():
    verifier, grant = _verifier()
    runtime = _blank_runtime(verifier)
    first = _contract("Intent A")
    second = _contract("Intent B")
    third = _contract("Intent C")
    receipt_b = _verified_receipt(verifier, grant, first, second, "revision-b")
    receipt_c = _verified_receipt(verifier, grant, second, third, "revision-c")

    runtime.install_integrity_contract(first)
    runtime.install_integrity_contract(
        second,
        supersedes_digest=first.digest,
        evolution_receipt=receipt_b,
    )
    runtime.install_integrity_contract(
        third,
        supersedes_digest=second.digest,
        evolution_receipt=receipt_c,
    )

    history = runtime.goal_revision_history(_GOAL_ID)
    entries = history.snapshot.entries
    assert tuple(entry.contract_digest for entry in entries) == (
        first.digest,
        second.digest,
        third.digest,
    )
    assert tuple(entry.ordinal for entry in entries) == (0, 1, 2)
    assert entries[1].previous_entry_digest == entries[0].entry_digest
    assert entries[2].previous_entry_digest == entries[1].entry_digest


def test_current_pointer_rewind_cannot_export_partial_historical_chain():
    runtime, original, _, _ = _verified_revision_runtime()

    with pytest.raises(ValueError, match="current head|linear goal chain"):
        _compile_from_runtime(runtime, current_digest=original.digest)


def test_missing_predecessor_and_cycle_fail_closed_before_export():
    runtime, original, revised, _ = _verified_revision_runtime()
    missing = dict(runtime._contract_predecessors)
    del missing[revised.digest]
    with pytest.raises(ValueError, match="predecessor mapping"):
        _compile_from_runtime(runtime, predecessors=missing)

    cycle = dict(runtime._contract_predecessors)
    cycle[original.digest] = revised.digest
    with pytest.raises(ValueError, match="cycle"):
        _compile_from_runtime(runtime, predecessors=cycle)


def test_cross_goal_predecessor_cannot_be_laundered_into_history():
    runtime, _, revised, _ = _verified_revision_runtime()
    foreign = _contract("Foreign goal intent", goal_id="goal:foreign")
    contracts = dict(runtime._integrity_contracts)
    contracts[foreign.digest] = foreign
    predecessors = dict(runtime._contract_predecessors)
    predecessors[revised.digest] = foreign.digest
    predecessors[foreign.digest] = None

    with pytest.raises(ValueError, match="crosses goal"):
        _compile_from_runtime(
            runtime,
            contracts=contracts,
            predecessors=predecessors,
        )


def test_tampered_evolution_receipt_cannot_enter_public_history():
    runtime, _, revised, receipt = _verified_revision_runtime()
    forged = deepcopy(receipt)
    object.__setattr__(forged, "freshness_ref", "freshness:forged")
    receipts = dict(runtime._evolution_receipts)
    receipts[revised.digest] = forged

    with pytest.raises(ValueError, match="receipt identity|mismatch"):
        _compile_from_runtime(runtime, receipts=receipts)


def test_trust_provenance_cannot_be_laundered_by_history_projection():
    runtime, _, revised, _ = _verified_revision_runtime()

    with pytest.raises(ValueError, match="legacy-unattested"):
        _compile_from_runtime(
            runtime,
            trust=lambda _digest: LEGACY_UNATTESTED_TRUST,
        )

    with pytest.raises(ValueError, match="verified trust"):
        _compile_from_runtime(
            runtime,
            receipts={},
            trust=lambda _digest: VERIFIED_CAPABILITY_AUTHORITY_TRUST,
        )

    legacy = _compile_from_runtime(
        runtime,
        receipts={},
        trust=lambda _digest: LEGACY_UNATTESTED_TRUST,
    )
    legacy_entry = legacy.snapshot.entries[1]
    assert legacy_entry.trust_label == LEGACY_UNATTESTED_TRUST
    assert legacy_entry.evolution_receipt_id is None
    assert legacy_entry.evidence_refs == ()
    assert legacy_entry.freshness_ref is None
    assert legacy_entry.confidence_milli is None


def test_explicit_historical_receipt_can_be_truthfully_labeled_legacy_unverified():
    runtime, _, _, receipt = _verified_revision_runtime()

    history = _compile_from_runtime(
        runtime,
        trust=lambda _digest: LEGACY_UNVERIFIED_AUTHORITY_TRUST,
    )
    entry = history.snapshot.entries[1]

    assert entry.trust_label == LEGACY_UNVERIFIED_AUTHORITY_TRUST
    assert entry.evolution_receipt_id == receipt.receipt_id
    assert entry.source_refs == receipt.source_refs
    assert entry.evidence_refs == receipt.evidence_refs
    assert entry.freshness_ref == receipt.freshness_ref
    assert entry.confidence_milli == receipt.confidence_milli


def test_restart_round_trip_preserves_history_and_receipt_identity():
    runtime, original, _, _ = _verified_revision_runtime()
    before = runtime.goal_revision_history(original.goal_id)
    state = runtime.integrity_state()

    restored = _blank_runtime(runtime.evolution_authority_verifier)
    restored.restore_integrity_state(state)
    after = restored.goal_revision_history(original.goal_id)

    assert tuple(entry.entry_digest for entry in after.snapshot.entries) == tuple(
        entry.entry_digest for entry in before.snapshot.entries
    )
    assert after.snapshot.history_digest == before.snapshot.history_digest
    assert after.receipt.receipt_id == before.receipt.receipt_id


def test_history_export_has_no_integrity_or_verifier_side_effects():
    runtime, original, _, _ = _verified_revision_runtime()
    before_state = deepcopy(runtime.integrity_state())
    before_verifier = deepcopy(runtime.evolution_authority_verifier.state())
    before_contracts = dict(runtime._integrity_contracts)
    before_predecessors = dict(runtime._contract_predecessors)

    runtime.goal_revision_history(original.goal_id)

    assert runtime.integrity_state() == before_state
    assert runtime.evolution_authority_verifier.state() == before_verifier
    assert runtime._integrity_contracts == before_contracts
    assert runtime._contract_predecessors == before_predecessors


def test_public_history_receipt_detects_post_export_tamper():
    runtime, original, _, _ = _verified_revision_runtime()
    history = deepcopy(runtime.goal_revision_history(original.goal_id))
    object.__setattr__(
        history.snapshot.entries[1],
        "evidence_refs",
        ("evidence:forged-after-export",),
    )

    with pytest.raises(ValueError, match="entry digest"):
        verify_goal_revision_history_export(history)
