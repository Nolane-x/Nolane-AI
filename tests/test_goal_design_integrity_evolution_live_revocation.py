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


def test_pre_revocation_proof_cannot_authorize_a_new_mutation_after_revocation():
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

    clock.value = 120
    verifier.revoke_grant(grant.grant_id)

    with pytest.raises(CoherenceError, match="revoked|live|current"):
        runtime.install_integrity_contract(
            revised,
            supersedes_digest=original.digest,
            evolution_receipt=receipt,
        )

    assert runtime.current_integrity_contract(original.goal_id) == original
    assert revised.digest not in runtime._integrity_contracts
