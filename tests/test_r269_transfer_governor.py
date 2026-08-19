from __future__ import annotations

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"


def _prior(expr=None):
    expr = expr or Binary("add", Field("a"), Field("b"))
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
        passed=True, structure=structure, expression=expr, probe_expressions=(),
        probe_candidates_considered=(), probe_validation_cases=2, probe_validation_exact=2,
        final_validation_cases=4, final_validation_exact=4, reason="verified_adaptive_basis",
        selected_basis_size=2, globally_minimal=True, false_accepts=0,
        trainable_parameter_count=0, oracle_calls_total=14,
        terminal_probe_validation_cases=0, terminal_probe_validation_exact=0,
    )
    return compile_r268_experience(
        receipt, source_authority_digest="authority.source", accepted_parent_sha=PARENT,
    )


def _signature():
    return PublicTaskSignature(
        role_names=("x", "y"), numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="grid.v1", budget_contract="diagnostic<=4;candidate<=256",
    )


def _diagnostics():
    return (
        {"x": 0, "y": 1}, {"x": 1, "y": 0}, {"x": 2, "y": 3},
        {"x": -2, "y": 4}, {"x": 5, "y": -1}, {"x": 3, "y": 7},
        {"x": 8, "y": 13}, {"x": -9, "y": -4}, {"x": 1, "y": 11},
        {"x": 17, "y": -6}, {"x": -15, "y": 2}, {"x": 23, "y": 5},
    )


def _terminal():
    return ({"x": 11, "y": 2}, {"x": -7, "y": 3}, {"x": 4, "y": 9})


def test_related_prior_succeeds_under_budget_where_complete_cold_scratch_remains_ambiguous():
    oracle = lambda row: row["x"] - row["y"]
    tight = MetaLearningConfig(
        max_diagnostic_queries=4, transfer_candidate_cap=32, scratch_candidate_cap=220,
        scratch_max_depth=2, min_scratch_partitions=2,
    )
    transfer = run_meta_learning_episode(
        (_prior(),), _signature(), _diagnostics(), _terminal(), oracle, tight,
    )
    scratch = run_cold_scratch(_signature(), _diagnostics(), _terminal(), oracle, tight)

    assert transfer.passed is True
    assert transfer.mode == "transfer"
    assert scratch.passed is False
    assert scratch.reason == "diagnostic_ambiguity"
    assert scratch.physical_terminal_calls == 0
    assert transfer.physical_diagnostic_calls <= scratch.physical_diagnostic_calls
    assert transfer.transfer_candidates_considered < scratch.scratch_candidates_considered
    assert transfer.false_accepts == scratch.false_accepts == 0


def test_terminal_evidence_cannot_resolve_diagnostic_ambiguity():
    oracle = lambda row: row["x"] + row["y"]
    config = MetaLearningConfig(
        max_diagnostic_queries=1, transfer_candidate_cap=16, scratch_candidate_cap=220,
        scratch_max_depth=2, min_scratch_partitions=2,
    )
    receipt = run_cold_scratch(
        _signature(), ({"x": 2, "y": 2},), _terminal(), oracle, config,
    )
    assert receipt.passed is False
    assert receipt.reason == "diagnostic_ambiguity"
    assert receipt.physical_terminal_calls == 0


def test_every_issued_transfer_probe_meets_scratch_information_floor():
    oracle = lambda row: row["x"] - row["y"]
    config = MetaLearningConfig(
        max_diagnostic_queries=4, transfer_candidate_cap=32, scratch_candidate_cap=220,
        scratch_max_depth=2, min_scratch_partitions=2,
    )
    receipt = run_meta_learning_episode(
        (_prior(),), _signature(), _diagnostics(), _terminal(), oracle, config,
    )
    diagnostic_rows = [row for row in receipt.ledger if row.phase == "diagnostic"]
    assert diagnostic_rows
    assert all(row.scratch_info_score >= 2 for row in diagnostic_rows)
