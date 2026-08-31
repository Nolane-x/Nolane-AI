from copy import deepcopy
from dataclasses import replace

import pytest

from nolane.external_core import _goal_design_integrity_runtime_v01 as legacy_runtime
from nolane.external_core.goal_design import CoherenceError
from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    EXPLICIT_EVOLUTION_TRUST,
    LEGACY_UNATTESTED_TRUST,
    mint_goal_integrity_evolution_receipt,
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
    runtime._evolution_receipts = {}
    runtime._legacy_unattested_evolution_digests = set()
    return runtime


def _receipt(predecessor: GoalIntegrityContract, successor: GoalIntegrityContract):
    return mint_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authority_ref="authority:goal-owner",
        reason="Explicitly revise the terminal-integrity contract after reviewed intent change.",
        source_refs=("source:user-intent:v2",),
        evidence_refs=("evidence:review:v2",),
        freshness_ref="freshness:2026-08-31T12:00:00Z",
        confidence_milli=1000,
    )


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
    assert revised.digest not in runtime._integrity_contracts


def test_explicit_evolution_receipt_is_deterministic_and_authorizes_exact_revision():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    receipt = _receipt(original, revised)

    assert receipt == _receipt(original, revised)
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )

    assert runtime.current_integrity_contract(original.goal_id) == revised
    assert runtime.evolution_receipt_for(revised.digest) == receipt
    assert runtime.evolution_trust_label(revised.digest) == EXPLICIT_EVOLUTION_TRUST


def test_tampered_evolution_receipt_fails_before_contract_state_mutates():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    receipt = _receipt(original, revised)
    tampered = replace(receipt, reason="Silently optimize a proxy instead.")

    runtime.install_integrity_contract(original)
    with pytest.raises(CoherenceError, match="evolution authority|identity|digest"):
        runtime.install_integrity_contract(
            revised,
            supersedes_digest=original.digest,
            evolution_receipt=tampered,
        )

    assert runtime.current_integrity_contract(original.goal_id) == original
    assert revised.digest not in runtime._integrity_contracts


def test_v2_evolution_state_round_trips_and_reverifies_receipt_after_restart():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    receipt = _receipt(original, revised)
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )

    state = runtime.integrity_state()
    assert state["schema_version"] == 2
    restored = _blank_runtime()
    restored.restore_integrity_state(state)

    assert restored.integrity_state() == state
    assert restored.evolution_receipt_for(revised.digest) == receipt
    assert restored.current_integrity_contract(original.goal_id) == revised


def test_restore_rejects_nested_receipt_tamper_even_if_outer_state_digest_is_recomputed():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=_receipt(original, revised),
    )
    tampered = deepcopy(runtime.integrity_state())
    tampered["evolution_receipts"][0]["receipt"]["reason"] = "laundered reason"
    payload = {key: value for key, value in tampered.items() if key != "state_digest"}
    tampered["state_digest"] = GoalIntegrityRuntime._state_digest(payload)

    restored = _blank_runtime()
    with pytest.raises(ValueError, match="evolution receipt|identity|digest"):
        restored.restore_integrity_state(tampered)

    assert restored._integrity_contracts == {}
    assert restored._evolution_receipts == {}


def test_restore_requires_provenance_for_every_v2_revision_edge():
    runtime = _blank_runtime()
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=_receipt(original, revised),
    )
    state = deepcopy(runtime.integrity_state())
    state["evolution_receipts"] = []
    payload = {key: value for key, value in state.items() if key != "state_digest"}
    state["state_digest"] = GoalIntegrityRuntime._state_digest(payload)

    restored = _blank_runtime()
    with pytest.raises(ValueError, match="every Goal/Design integrity revision|provenance"):
        restored.restore_integrity_state(state)

    assert restored._integrity_contracts == {}


def test_legacy_v1_revision_restores_without_fabricated_evidence_and_is_labeled():
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's historical revised terminal intent.")

    historical = legacy_runtime.GoalIntegrityRuntime.__new__(legacy_runtime.GoalIntegrityRuntime)
    historical.integrity_authority = legacy_runtime.GoalIntegrityAuthorityIndex()
    historical._integrity_contracts = {}
    historical._current_contracts = {}
    historical._contract_predecessors = {}
    historical.install_integrity_contract(original)
    historical.install_integrity_contract(revised, supersedes_digest=original.digest)
    legacy_state = historical.integrity_state()
    assert legacy_state["schema_version"] == 1

    restored = _blank_runtime()
    restored.restore_integrity_state(legacy_state)

    assert restored.current_integrity_contract(original.goal_id) == revised
    assert restored.evolution_trust_label(revised.digest) == LEGACY_UNATTESTED_TRUST
    assert restored.integrity_state()["schema_version"] == 2
    assert restored.integrity_state()["legacy_unattested_evolution_digests"] == (revised.digest,)
