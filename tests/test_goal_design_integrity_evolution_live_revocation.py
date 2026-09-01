import pytest

from nolane.external_core.goal_design import CoherenceError
from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    mint_verified_goal_integrity_evolution_receipt,
)
from nolane.external_core.goal_design_integrity_evolution_authority import (
    GOAL_INTEGRITY_EVOLUTION_ACTION,
    GoalIntegrityEvolutionAuthorityVerifier,
)
from nolane.external_core.goal_design_integrity_runtime import (
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)


class _Clock:
    def __init__(self, value: int) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


def _contract(statement: str) -> GoalIntegrityContract:
    goal_id = "goal:live-revocation"
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
        ),
    )


def _runtime(verifier: GoalIntegrityEvolutionAuthorityVerifier) -> GoalIntegrityRuntime:
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


def _prepared_transition(*, can_delegate: bool = False, depth: int = 0):
    clock = _Clock(100)
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=b"live-revocation-authority-key-32b",
        clock=clock,
    )
    original = _contract("Preserve terminal intent.")
    revised = _contract("Preserve the reviewed revised terminal intent.")
    grant = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=(original.goal_id,),
        valid_from_epoch_s=50,
        valid_until_epoch_s=500,
        can_delegate=can_delegate,
        delegation_depth_remaining=depth,
    )
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=original,
        successor=revised,
    )
    receipt = mint_verified_goal_integrity_evolution_receipt(
        predecessor=original,
        successor=revised,
        authorization_proof=proof,
        reason="Reviewed revision authorized before later revocation.",
        source_refs=("source:reviewed-intent",),
        evidence_refs=("evidence:pre-revocation-proof",),
        freshness_ref="freshness:pre-revocation",
    )
    runtime = _runtime(verifier)
    runtime.install_integrity_contract(original)
    return clock, verifier, grant, original, revised, receipt, runtime


def _assert_live_mutation_rejected(runtime, original, revised, receipt):
    with pytest.raises(CoherenceError, match="revoked|live|current|clock"):
        runtime.install_integrity_contract(
            revised,
            supersedes_digest=original.digest,
            evolution_receipt=receipt,
        )

    assert runtime.current_integrity_contract(original.goal_id) == original
    assert revised.digest not in runtime._integrity_contracts


def test_pre_revocation_proof_cannot_authorize_a_new_mutation_after_revocation():
    clock, verifier, grant, original, revised, receipt, runtime = _prepared_transition()

    clock.value = 120
    verifier.revoke_grant(grant.grant_id)

    _assert_live_mutation_rejected(runtime, original, revised, receipt)


def test_live_revocation_cannot_be_bypassed_by_authority_clock_rollback():
    clock, verifier, grant, original, revised, receipt, runtime = _prepared_transition()

    clock.value = 120
    verifier.revoke_grant(grant.grant_id)
    clock.value = 110

    _assert_live_mutation_rejected(runtime, original, revised, receipt)


def test_revocation_timestamp_is_immutable_under_clock_rollback_and_history_stays_valid():
    clock, verifier, grant, original, revised, receipt, _ = _prepared_transition()

    clock.value = 120
    assert verifier.revoke_grant(grant.grant_id) == 120
    clock.value = 90
    assert verifier.revoke_grant(grant.grant_id) == 120

    verifier.verify_contract_transition(
        receipt.authority_ref,
        predecessor=original,
        successor=revised,
    )


def test_revoked_grant_cannot_issue_new_proof_after_clock_rollback():
    clock, verifier, grant, original, revised, _, _ = _prepared_transition()

    clock.value = 120
    verifier.revoke_grant(grant.grant_id)
    clock.value = 110

    with pytest.raises(ValueError, match="revoked"):
        verifier.authorize_contract_transition(
            grant.grant_id,
            predecessor=original,
            successor=revised,
        )


def test_revoked_parent_cannot_delegate_after_clock_rollback():
    clock, verifier, grant, original, _, _, _ = _prepared_transition(
        can_delegate=True,
        depth=1,
    )

    clock.value = 120
    verifier.revoke_grant(grant.grant_id)
    clock.value = 110

    with pytest.raises(ValueError, match="revoked"):
        verifier.delegate_grant(
            grant.grant_id,
            subject_ref="authority:delegate-after-revoke",
            goal_ids=(original.goal_id,),
            actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
            valid_from_epoch_s=60,
            valid_until_epoch_s=400,
        )
