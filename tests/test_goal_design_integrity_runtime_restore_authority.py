import pytest

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

_AUTHORITY_KEY = b"restore-authority-test-key-32bytes"


def _contract(statement: str) -> GoalIntegrityContract:
    return GoalIntegrityContract(
        goal_id="goal:restore-authority",
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                "goal:restore-authority",
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:terminal",
            ),
        ),
    )


def _authority():
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=lambda: 100,
    )
    grant = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=("goal:restore-authority",),
        valid_from_epoch_s=0,
        valid_until_epoch_s=1000,
    )
    return verifier, grant


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


def _evolution(verifier, grant, predecessor, successor):
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=predecessor,
        successor=successor,
    )
    return mint_verified_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authorization_proof=proof,
        reason="Reviewed restore-authority revision.",
        source_refs=("source:goal-owner",),
        evidence_refs=("evidence:restore-review",),
        freshness_ref="freshness:test:v3",
    )


def test_restore_rejects_reactivation_of_historical_integrity_contract():
    verifier, grant = _authority()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve terminal intent.")
    revised = _contract("Preserve terminal intent and reversible user control.")

    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=_evolution(verifier, grant, original, revised),
    )
    state = runtime.integrity_state()

    state["current_contracts"][original.goal_id] = original.digest
    payload = {key: value for key, value in state.items() if key != "state_digest"}
    state["state_digest"] = GoalIntegrityRuntime._state_digest_v3(payload)

    restored = _blank_runtime(verifier)
    with pytest.raises(ValueError, match="historical|head|reactivat|supersed"):
        restored.restore_integrity_state(state)
