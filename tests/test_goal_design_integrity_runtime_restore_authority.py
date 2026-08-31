import pytest

from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    mint_goal_integrity_evolution_receipt,
)
from nolane.external_core.goal_design_integrity_runtime import (
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)


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


def _blank_runtime() -> GoalIntegrityRuntime:
    runtime = GoalIntegrityRuntime.__new__(GoalIntegrityRuntime)
    runtime.integrity_authority = GoalIntegrityAuthorityIndex()
    runtime._integrity_contracts = {}
    runtime._current_contracts = {}
    runtime._contract_predecessors = {}
    runtime._evolution_receipts = {}
    runtime._legacy_unattested_evolution_digests = set()
    return runtime


def _evolution(predecessor, successor):
    return mint_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authority_ref="authority:goal-owner",
        reason="Reviewed restore-authority revision.",
        source_refs=("source:goal-owner",),
        evidence_refs=("evidence:restore-review",),
        freshness_ref="freshness:test:v2",
    )


def test_restore_rejects_reactivation_of_historical_integrity_contract():
    runtime = _blank_runtime()
    original = _contract("Preserve terminal intent.")
    revised = _contract("Preserve terminal intent and reversible user control.")

    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=_evolution(original, revised),
    )
    state = runtime.integrity_state()

    state["current_contracts"][original.goal_id] = original.digest
    payload = {key: value for key, value in state.items() if key != "state_digest"}
    state["state_digest"] = GoalIntegrityRuntime._state_digest(payload)

    restored = _blank_runtime()
    with pytest.raises(ValueError, match="historical|head|reactivat|supersed"):
        restored.restore_integrity_state(state)
