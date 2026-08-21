from __future__ import annotations

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PriorRegistry,
    PublicTaskSignature,
    match_portable_experiences,
    run_cold_scratch,
    run_meta_learning_episode,
)

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"


def _prior():
    structure = AdaptiveCausalBasisStructureReceipt(
        passed=True, selected=None, selected_basis_size=2, globally_minimal=True,
        necessity_certificates=(), unresolved_lower_order=(), legal_interventions=2,
        semantic_profiles=2, intervention_candidates_considered=2, bases_considered=1,
        composition_candidates_considered=4, oracle_calls=8, false_accepts=0,
        reason="adaptive_basis_discovered", lower_basis_count=0, lower_basis_certified=0,
        lower_basis_inconclusive=0, lower_basis_universe_digest="lower", proof_ledger_complete=True,
        lower_basis_certificates=(), trainable_parameter_count=0,
    )
    receipt = AdaptiveCausalBasisReceipt(
        passed=True, structure=structure, expression=Binary("add", Field("a"), Field("b")),
        probe_expressions=(), probe_candidates_considered=(), probe_validation_cases=2,
        probe_validation_exact=2, final_validation_cases=4, final_validation_exact=4,
        reason="verified_adaptive_basis", selected_basis_size=2, globally_minimal=True,
        false_accepts=0, trainable_parameter_count=0, oracle_calls_total=14,
        terminal_probe_validation_cases=0, terminal_probe_validation_exact=0,
    )
    return compile_r268_experience(
        receipt, verifier_evidence_digest="verifier.fixture.authority.source", accepted_parent_sha=PARENT,
    )


def _signature():
    return PublicTaskSignature(
        role_names=("x", "y"), numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="grid.v2", budget_contract="diagnostic<=5;candidate<=256",
    )


def test_wrong_prior_falls_back_to_scratch_without_replaying_observations_and_is_quarantined():
    prior = _prior()
    registry = PriorRegistry()
    diagnostics = (
        {"x": 0, "y": 1}, {"x": 1, "y": 0}, {"x": 2, "y": 3},
        {"x": -2, "y": 4}, {"x": 5, "y": -1}, {"x": 3, "y": 7},
        {"x": 8, "y": 2},
    )
    terminal = ({"x": 11, "y": 2}, {"x": -7, "y": 3}, {"x": 4, "y": 9})
    oracle = lambda row: (row["x"] * row["y"]) + row["x"]
    config = MetaLearningConfig(
        max_diagnostic_queries=5, transfer_candidate_cap=24, scratch_candidate_cap=256,
        scratch_max_depth=2, min_scratch_partitions=2,
    )

    receipt = run_meta_learning_episode(
        (prior,), _signature(), diagnostics, terminal, oracle, config, registry=registry,
    )
    cold = run_cold_scratch(_signature(), diagnostics, terminal, oracle, config)

    assert receipt.passed is True
    assert receipt.mode == "scratch_after_transfer"
    assert receipt.reused_observations >= 1
    assert receipt.physical_diagnostic_calls <= cold.physical_diagnostic_calls + 1
    assert receipt.quarantine_action is True
    assert prior.portable_digest in registry.quarantined_prior_digests

    rows = match_portable_experiences(
        (prior,), _signature(), quarantined_prior_digests=registry.quarantined_prior_digests,
    )
    assert rows[0].compatible is False
    assert rows[0].reason == "prior_quarantined"


def test_no_compatible_prior_enters_cold_scratch_directly():
    prior = _prior()
    signature = PublicTaskSignature(
        role_names=("a", "b", "c"), numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul"), query_space_digest="q3",
        budget_contract="diagnostic<=4;candidate<=256",
    )
    diagnostics = (
        {"a": 1, "b": 2, "c": 3}, {"a": 2, "b": 1, "c": 4},
        {"a": 3, "b": 5, "c": 2}, {"a": -1, "b": 3, "c": 2},
    )
    terminal = ({"a": 7, "b": 2, "c": 5}, {"a": 4, "b": 6, "c": 1})
    oracle = lambda row: row["a"] + row["b"] + row["c"]
    config = MetaLearningConfig(
        max_diagnostic_queries=4, transfer_candidate_cap=24, scratch_candidate_cap=256,
        scratch_max_depth=2, min_scratch_partitions=2,
    )
    receipt = run_meta_learning_episode((prior,), signature, diagnostics, terminal, oracle, config)
    assert receipt.mode == "scratch"
    assert receipt.selected_prior_digest is None
    assert receipt.transfer_candidates_considered == 0
