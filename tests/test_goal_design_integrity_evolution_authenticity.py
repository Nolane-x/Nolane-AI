import pytest

from nolane.external_core.goal_design import CoherenceError
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
        goal_id="goal:evolution-authenticity",
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                "goal:evolution-authenticity",
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:terminal",
            ),
            GoalIntegrityClause(
                "constraint:user-control",
                "goal:evolution-authenticity",
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Preserve explicit user control.",
                "prov:user-control",
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
