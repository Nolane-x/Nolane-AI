from copy import deepcopy

import pytest

from nolane.external_core.goal_design import CoherenceError
from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    mint_goal_integrity_evolution_receipt,
    mint_verified_goal_integrity_evolution_receipt,
)
from nolane.external_core.goal_design_integrity_evolution_authority import (
    GOAL_INTEGRITY_EVOLUTION_ACTION,
    GoalIntegrityEvolutionAuthorityVerifier,
)
from nolane.external_core.goal_design_integrity_runtime import (
    VERIFIED_CAPABILITY_AUTHORITY_TRUST,
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)

_AUTHORITY_KEY = b"authenticity-test-authority-key-32b"


class _Clock:
    def __init__(self, value: int = 100) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


def _contract(statement: str, *, goal_id: str = "goal:evolution-authenticity") -> GoalIntegrityContract:
    return GoalIntegrityContract(
        goal_id=goal_id,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                goal_id,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:terminal",
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


def _verifier(clock=None):
    clock = _Clock() if clock is None else clock
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=clock,
    )
    return verifier, clock


def _grant(verifier, *, goal_ids=("goal:evolution-authenticity",), can_delegate=False, depth=0):
    return verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=goal_ids,
        actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s=50,
        valid_until_epoch_s=500,
        can_delegate=can_delegate,
        delegation_depth_remaining=depth,
    )


def _blank_runtime(verifier=None) -> GoalIntegrityRuntime:
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


def _verified_receipt(verifier, grant, predecessor, successor):
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=predecessor,
        successor=successor,
    )
    receipt = mint_verified_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authorization_proof=proof,
        reason="Reviewed and independently authorized terminal-integrity revision.",
        source_refs=("source:reviewed-intent",),
        evidence_refs=("evidence:authority-proof",),
        freshness_ref="freshness:verified",
    )
    return proof, receipt


def test_self_asserted_authority_ref_cannot_authorize_integrity_evolution():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's reviewed revised terminal intent.")
    forged = mint_goal_integrity_evolution_receipt(
        predecessor=original,
        successor=revised,
        authority_ref="authority:forged-owner",
        reason="Caller claims to be the goal owner without independent authority proof.",
        source_refs=("source:caller-claim",),
        evidence_refs=("evidence:self-asserted",),
        freshness_ref="freshness:self-asserted",
        confidence_milli=1000,
    )

    runtime.install_integrity_contract(original)

    with pytest.raises(CoherenceError, match="authentic|verifier|authority proof|capability"):
        runtime.install_integrity_contract(
            revised,
            supersedes_digest=original.digest,
            evolution_receipt=forged,
        )

    assert runtime.current_integrity_contract(original.goal_id) == original
    assert revised.digest not in runtime._integrity_contracts


def test_verifier_issued_transition_bound_proof_authorizes_revision():
    verifier, _ = _verifier()
    grant = _grant(verifier)
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve reviewed revised terminal intent.")
    proof, receipt = _verified_receipt(verifier, grant, original, revised)

    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )

    assert receipt.authority_ref == proof.proof_id
    assert runtime.current_integrity_contract(original.goal_id) == revised
    assert runtime.evolution_trust_label(revised.digest) == VERIFIED_CAPABILITY_AUTHORITY_TRUST


def test_authorization_proof_cannot_be_reused_for_another_transition():
    verifier, _ = _verifier()
    grant = _grant(verifier)
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve reviewed revised terminal intent.")
    another = _contract("Preserve a third reviewed terminal intent.")
    proof, _ = _verified_receipt(verifier, grant, original, revised)

    with pytest.raises(ValueError, match="successor|delta|mismatch"):
        verifier.verify_contract_transition(
            proof.proof_id,
            predecessor=original,
            successor=another,
        )


def test_goal_scope_and_verifier_clock_are_fail_closed():
    clock = _Clock(100)
    verifier, _ = _verifier(clock)
    wrong_goal_grant = _grant(verifier, goal_ids=("goal:other",))
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve reviewed revised terminal intent.")

    with pytest.raises(ValueError, match="does not cover goal"):
        verifier.authorize_contract_transition(
            wrong_goal_grant.grant_id,
            predecessor=original,
            successor=revised,
        )

    future = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:future-owner",
        goal_ids=(original.goal_id,),
        valid_from_epoch_s=200,
        valid_until_epoch_s=300,
    )
    with pytest.raises(ValueError, match="validity window"):
        verifier.authorize_contract_transition(
            future.grant_id,
            predecessor=original,
            successor=revised,
        )

    clock.value = 600
    valid_then_expired = _grant(verifier)
    with pytest.raises(ValueError, match="validity window"):
        verifier.authorize_contract_transition(
            valid_then_expired.grant_id,
            predecessor=original,
            successor=revised,
        )


def test_delegation_cannot_broaden_parent_scope_validity_or_depth():
    verifier, _ = _verifier()
    parent = _grant(verifier, can_delegate=True, depth=2)

    child = verifier.delegate_grant(
        parent.grant_id,
        subject_ref="authority:delegate",
        goal_ids=("goal:evolution-authenticity",),
        actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s=60,
        valid_until_epoch_s=400,
        can_delegate=True,
        delegation_depth_remaining=1,
    )
    assert child.parent_grant_id == parent.grant_id

    with pytest.raises(ValueError, match="goal scope broadens"):
        verifier.delegate_grant(
            parent.grant_id,
            subject_ref="authority:bad-goal",
            goal_ids=("goal:evolution-authenticity", "goal:other"),
            actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
            valid_from_epoch_s=60,
            valid_until_epoch_s=400,
        )

    with pytest.raises(ValueError, match="validity broadens"):
        verifier.delegate_grant(
            parent.grant_id,
            subject_ref="authority:bad-time",
            goal_ids=("goal:evolution-authenticity",),
            actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
            valid_from_epoch_s=0,
            valid_until_epoch_s=400,
        )

    with pytest.raises(ValueError, match="depth broadens"):
        verifier.delegate_grant(
            parent.grant_id,
            subject_ref="authority:bad-depth",
            goal_ids=("goal:evolution-authenticity",),
            actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
            valid_from_epoch_s=60,
            valid_until_epoch_s=400,
            can_delegate=True,
            delegation_depth_remaining=2,
        )


def test_ancestor_revocation_blocks_future_descendant_proofs_but_not_prior_history():
    clock = _Clock(100)
    verifier, _ = _verifier(clock)
    parent = _grant(verifier, can_delegate=True, depth=1)
    child = verifier.delegate_grant(
        parent.grant_id,
        subject_ref="authority:delegate",
        goal_ids=("goal:evolution-authenticity",),
        actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s=60,
        valid_until_epoch_s=400,
    )
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve reviewed revised terminal intent.")
    proof = verifier.authorize_contract_transition(
        child.grant_id,
        predecessor=original,
        successor=revised,
    )

    clock.value = 120
    verifier.revoke_grant(parent.grant_id)
    verifier.verify_contract_transition(
        proof.proof_id,
        predecessor=original,
        successor=revised,
    )

    clock.value = 130
    with pytest.raises(ValueError, match="revoked"):
        verifier.authorize_contract_transition(
            child.grant_id,
            predecessor=original,
            successor=revised,
        )


def test_authority_registry_round_trip_preserves_proofs_without_serializing_key():
    verifier, clock = _verifier()
    grant = _grant(verifier)
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve reviewed revised terminal intent.")
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=original,
        successor=revised,
    )
    state = verifier.state()

    assert "authority_key" not in state
    restored = GoalIntegrityEvolutionAuthorityVerifier.restore_state(
        state,
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=clock,
    )
    assert restored.proof(proof.proof_id) == proof
    restored.verify_contract_transition(
        proof.proof_id,
        predecessor=original,
        successor=revised,
    )


def test_authority_state_tamper_fails_even_if_public_digest_is_recomputed():
    verifier, clock = _verifier()
    grant = _grant(verifier)
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve reviewed revised terminal intent.")
    verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=original,
        successor=revised,
    )
    tampered = deepcopy(verifier.state())
    tampered["grants"][0]["subject_ref"] = "authority:attacker"
    payload = {
        "schema_version": tampered["schema_version"],
        "grants": tampered["grants"],
        "revocations": tampered["revocations"],
        "proofs": tampered["proofs"],
    }
    tampered["state_digest"] = GoalIntegrityEvolutionAuthorityVerifier._state_digest(payload)

    with pytest.raises(ValueError, match="authenticator"):
        GoalIntegrityEvolutionAuthorityVerifier.restore_state(
            tampered,
            trusted_root_issuers=("authority:root",),
            authority_key=_AUTHORITY_KEY,
            clock=clock,
        )


def test_signed_pre_revocation_snapshot_cannot_rollback_newer_authority_checkpoint():
    verifier, clock = _verifier()
    grant = _grant(verifier)
    old_state = verifier.state()

    clock.value = 120
    verifier.revoke_grant(grant.grant_id)
    current_state = verifier.state()
    assert current_state["state_digest"] != old_state["state_digest"]

    with pytest.raises(ValueError, match="rollback|checkpoint|expected state"):
        GoalIntegrityEvolutionAuthorityVerifier.restore_state(
            old_state,
            trusted_root_issuers=("authority:root",),
            authority_key=_AUTHORITY_KEY,
            clock=clock,
            expected_state_digest=current_state["state_digest"],
        )
