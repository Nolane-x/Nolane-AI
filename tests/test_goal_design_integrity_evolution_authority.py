from copy import deepcopy
from dataclasses import replace

import pytest

from nolane.external_core import _goal_design_integrity_runtime_v01 as legacy_runtime
from nolane.external_core import _goal_design_integrity_runtime_v02 as accepted_v02_runtime
from nolane.external_core.goal_design import CoherenceError
from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    LEGACY_UNATTESTED_TRUST,
    mint_goal_integrity_evolution_receipt,
    mint_verified_goal_integrity_evolution_receipt,
)
from nolane.external_core.goal_design_integrity_evolution_authority import (
    GoalIntegrityEvolutionAuthorityVerifier,
)
from nolane.external_core.goal_design_integrity_runtime import (
    LEGACY_UNVERIFIED_AUTHORITY_TRUST,
    VERIFIED_CAPABILITY_AUTHORITY_TRUST,
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)

_AUTHORITY_KEY = b"goal-design-evolution-test-key-32b"


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


def _authority():
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=lambda: 100,
    )
    grant = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=("goal:evolution-authority",),
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


def _receipt(predecessor, successor, verifier, grant):
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=predecessor,
        successor=successor,
    )
    return mint_verified_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authorization_proof=proof,
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
        runtime.install_integrity_contract(revised, supersedes_digest=original.digest)

    assert runtime.current_integrity_contract(original.goal_id) == original
    assert revised.digest not in runtime._integrity_contracts


def test_verified_evolution_receipt_is_deterministic_and_authorizes_exact_revision():
    verifier, grant = _authority()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    receipt = _receipt(original, revised, verifier, grant)

    assert receipt == _receipt(original, revised, verifier, grant)
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )

    assert runtime.current_integrity_contract(original.goal_id) == revised
    assert runtime.evolution_receipt_for(revised.digest) == receipt
    assert runtime.evolution_trust_label(revised.digest) == VERIFIED_CAPABILITY_AUTHORITY_TRUST


def test_tampered_evolution_receipt_fails_before_contract_state_mutates():
    verifier, grant = _authority()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    receipt = _receipt(original, revised, verifier, grant)
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


def test_v3_evolution_state_round_trips_and_reverifies_capability_after_restart():
    verifier, grant = _authority()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    receipt = _receipt(original, revised, verifier, grant)
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )

    state = runtime.integrity_state()
    assert state["schema_version"] == 3
    restored = _blank_runtime(verifier)
    restored.restore_integrity_state(state)

    assert restored.integrity_state() == state
    assert restored.evolution_receipt_for(revised.digest) == receipt
    assert restored.current_integrity_contract(original.goal_id) == revised
    assert restored.evolution_trust_label(revised.digest) == VERIFIED_CAPABILITY_AUTHORITY_TRUST


def test_restore_rejects_nested_receipt_tamper_even_if_outer_state_digest_is_recomputed():
    verifier, grant = _authority()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=_receipt(original, revised, verifier, grant),
    )
    tampered = deepcopy(runtime.integrity_state())
    tampered["evolution_receipts"][0]["receipt"]["reason"] = "laundered reason"
    payload = {key: value for key, value in tampered.items() if key != "state_digest"}
    tampered["state_digest"] = GoalIntegrityRuntime._state_digest_v3(payload)

    restored = _blank_runtime(verifier)
    with pytest.raises(ValueError, match="evolution receipt|identity|digest"):
        restored.restore_integrity_state(tampered)

    assert restored._integrity_contracts == {}
    assert restored._evolution_receipts == {}


def test_restore_requires_exactly_one_provenance_class_for_every_v3_revision_edge():
    verifier, grant = _authority()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's revised explicit terminal intent.")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=_receipt(original, revised, verifier, grant),
    )
    state = deepcopy(runtime.integrity_state())
    state["verified_capability_evolution_digests"] = ()
    payload = {key: value for key, value in state.items() if key != "state_digest"}
    state["state_digest"] = GoalIntegrityRuntime._state_digest_v3(payload)

    restored = _blank_runtime(verifier)
    with pytest.raises(ValueError, match="every receipted|provenance"):
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
    migrated = restored.integrity_state()
    assert migrated["schema_version"] == 3
    assert migrated["legacy_unattested_evolution_digests"] == (revised.digest,)
    assert migrated["legacy_unverified_authority_digests"] == ()


def test_legacy_v2_receipt_migrates_as_unverified_without_fabricating_capability_trust():
    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's v2 revised terminal intent.")
    historical = accepted_v02_runtime.GoalIntegrityRuntime.__new__(
        accepted_v02_runtime.GoalIntegrityRuntime
    )
    historical.integrity_authority = accepted_v02_runtime.GoalIntegrityAuthorityIndex()
    historical._integrity_contracts = {}
    historical._current_contracts = {}
    historical._contract_predecessors = {}
    historical._evolution_receipts = {}
    historical._legacy_unattested_evolution_digests = set()
    old_receipt = mint_goal_integrity_evolution_receipt(
        predecessor=original,
        successor=revised,
        authority_ref="authority:historical-unverified-owner",
        reason="Historical v2 explicit receipt predating authenticity verification.",
        source_refs=("source:historical",),
        evidence_refs=("evidence:historical",),
        freshness_ref="freshness:v2-history",
    )
    historical.install_integrity_contract(original)
    historical.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=old_receipt,
    )
    v2_state = historical.integrity_state()
    assert v2_state["schema_version"] == 2

    restored = _blank_runtime()
    restored.restore_integrity_state(v2_state)

    assert restored.evolution_receipt_for(revised.digest) == old_receipt
    assert restored.evolution_trust_label(revised.digest) == LEGACY_UNVERIFIED_AUTHORITY_TRUST
    migrated = restored.integrity_state()
    assert migrated["schema_version"] == 3
    assert migrated["legacy_unverified_authority_digests"] == (revised.digest,)
    assert migrated["verified_capability_evolution_digests"] == ()
