from __future__ import annotations

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PriorRegistry,
    PublicTaskSignature,
    match_portable_experiences,
    run_meta_learning_episode,
)

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"


def _receipt(expr, size: int, label: str) -> AdaptiveCausalBasisReceipt:
    structure = AdaptiveCausalBasisStructureReceipt(
        passed=True,
        selected=None,
        selected_basis_size=size,
        globally_minimal=True,
        necessity_certificates=(),
        unresolved_lower_order=(),
        legal_interventions=size,
        semantic_profiles=size,
        intervention_candidates_considered=size,
        bases_considered=1,
        composition_candidates_considered=8,
        oracle_calls=12,
        false_accepts=0,
        reason="adaptive_basis_discovered",
        lower_basis_count=max(0, size - 1),
        lower_basis_certified=max(0, size - 1),
        lower_basis_inconclusive=0,
        lower_basis_universe_digest=f"lower.{label}",
        proof_ledger_complete=True,
        lower_basis_certificates=(),
        trainable_parameter_count=0,
    )
    return AdaptiveCausalBasisReceipt(
        passed=True,
        structure=structure,
        expression=expr,
        probe_expressions=(),
        probe_candidates_considered=(),
        probe_validation_cases=4,
        probe_validation_exact=4,
        final_validation_cases=6,
        final_validation_exact=6,
        reason="verified_adaptive_basis",
        selected_basis_size=size,
        globally_minimal=True,
        false_accepts=0,
        trainable_parameter_count=0,
        oracle_calls_total=22,
        terminal_probe_validation_cases=0,
        terminal_probe_validation_exact=0,
    )


def _prior(expr, label: str):
    return compile_r268_experience(
        _receipt(expr, 2, label),
        source_authority_digest=f"authority.{label}",
        accepted_parent_sha=PARENT,
    )


def _signature() -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=("x", "y"),
        numeric_domain="finite_integer",
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="r269.test.multi-prior.complete-domain",
        budget_contract="diagnostic<=4;candidate<=128",
        finite_integer_values=(-3, -1, 2, 5),
    )


def test_multiple_compatible_priors_are_adjudicated_by_target_evidence_not_preselected_score():
    a, b = Field("a"), Field("b")
    correct = _prior(Binary("add", a, b), "simple-add")
    misleading = _prior(Binary("add", Binary("mul", a, b), a), "misleading-topology")
    signature = _signature()

    matches = match_portable_experiences((correct, misleading), signature)
    compatible = [row for row in matches if row.compatible]
    assert len(compatible) == 2
    # The current public-structure score prefers the more complicated prior.
    # The runtime must therefore use target evidence to recover the correct one
    # rather than treating this pre-evidence ranking as authority.
    assert compatible[0].portable.portable_digest == misleading.portable_digest

    diagnostics = (
        {"x": -3, "y": 5},
        {"x": 2, "y": -1},
        {"x": 5, "y": 2},
        {"x": -1, "y": -3},
    )
    terminal = (
        {"x": 2, "y": 5},
        {"x": -3, "y": -1},
    )
    registry = PriorRegistry()
    config = MetaLearningConfig(
        max_diagnostic_queries=4,
        transfer_candidate_cap=128,
        scratch_candidate_cap=128,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )

    receipt = run_meta_learning_episode(
        (misleading, correct),
        signature,
        diagnostics,
        terminal,
        lambda row: row["x"] + row["y"],
        config,
        registry=registry,
    )

    assert receipt.passed is True
    assert receipt.mode == "transfer"
    assert receipt.selected_prior_digest == correct.portable_digest
    assert receipt.transfer_contradictions == 0
    assert registry.state_for(correct.portable_digest).status == "active"
    assert registry.state_for(misleading.portable_digest).status in ("active", "quarantined")
    assert receipt.false_accepts == 0


def test_multi_prior_adjudication_is_insertion_order_invariant():
    a, b = Field("a"), Field("b")
    correct = _prior(Binary("add", a, b), "simple-add-order")
    misleading = _prior(Binary("add", Binary("mul", a, b), a), "misleading-order")
    signature = _signature()
    diagnostics = (
        {"x": -3, "y": 5},
        {"x": 2, "y": -1},
        {"x": 5, "y": 2},
        {"x": -1, "y": -3},
    )
    terminal = ({"x": 2, "y": 5}, {"x": -3, "y": -1})
    config = MetaLearningConfig(
        max_diagnostic_queries=4,
        transfer_candidate_cap=128,
        scratch_candidate_cap=128,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )

    def run(priors):
        return run_meta_learning_episode(
            priors,
            signature,
            diagnostics,
            terminal,
            lambda row: row["x"] + row["y"],
            config,
            registry=PriorRegistry(),
        )

    forward = run((correct, misleading))
    reverse = run((misleading, correct))
    assert forward.passed is reverse.passed is True
    assert forward.mode == reverse.mode == "transfer"
    assert forward.selected_prior_digest == reverse.selected_prior_digest == correct.portable_digest
    assert forward.physical_diagnostic_calls == reverse.physical_diagnostic_calls
    assert forward.false_accepts == reverse.false_accepts == 0
