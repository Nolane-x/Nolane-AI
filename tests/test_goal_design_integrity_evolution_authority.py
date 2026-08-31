import pytest

from nolane.external_core.goal_design import CoherenceError
from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_runtime import (
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)


def _contract(statement: str) -> GoalIntegrityContract:
    return GoalIntegrityContract(
        goal_id="goal:evolution-authority",
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                "goal:evolution-authority",
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:terminal",
            ),
            GoalIntegrityClause(
                "constraint:user-control",
                "goal:evolution-authority",
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
    return runtime


def test_terminal_semantic_rewrite_requires_explicit_evolution_authority():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Optimize the proxy score even when user intent changes.")

    runtime.install_integrity_contract(original)

    with pytest.raises(CoherenceError, match="evolution|revision|semantic|terminal"):
        runtime.install_integrity_contract(
            revised,
            supersedes_digest=original.digest,
        )

    assert runtime.current_integrity_contract(original.goal_id) == original
