from __future__ import annotations

import json
from dataclasses import replace

import pytest

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import portable_experience_from_data
from cogcoder.r269_experience_compiler import compile_meta_learning_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PublicTaskSignature,
    match_portable_experiences,
    run_cold_scratch,
    run_meta_learning_episode,
)

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"
DOMAIN = (-2, 0, 3, 5)
OPS = ("add", "sub", "mul", "min", "max")


def _signature(names: tuple[str, str], *, domain: tuple[int, ...] = DOMAIN) -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=names,
        numeric_domain="finite_integer",
        allowed_binary_ops=OPS,
        query_space_digest="r269.sequential.complete-domain.v2",
        budget_contract="diagnostic<=4;candidate<=256",
        finite_integer_values=domain,
    )


def _contexts(names: tuple[str, str]):
    a, b = names
    diagnostics = (
        {a: -2, b: 3},
        {a: 0, b: 5},
        {a: 3, b: -2},
        {a: 5, b: 0},
    )
    terminal = ({a: 3, b: 5}, {a: -2, b: 0})
    return diagnostics, terminal


def _config() -> MetaLearningConfig:
    return MetaLearningConfig(
        max_diagnostic_queries=4,
        transfer_candidate_cap=64,
        scratch_candidate_cap=256,
        scratch_max_depth=1,
        min_scratch_partitions=2,
    )


def _accepted_episode(names: tuple[str, str], op: str = "add"):
    signature = _signature(names)
    diagnostics, terminal = _contexts(names)
    a, b = names

    def oracle(row):
        if op == "add":
            return row[a] + row[b]
        if op == "sub":
            return row[a] - row[b]
        raise ValueError(op)

    receipt = run_cold_scratch(signature, diagnostics, terminal, oracle, _config())
    assert receipt.passed is True
    assert receipt.mode == "scratch"
    assert receipt.physical_terminal_calls == len(terminal)
    return signature, receipt


def test_verified_target_episode_compiles_to_identity_free_authority_bound_portable_experience():
    signature, receipt = _accepted_episode(("source_left", "source_right"))
    portable = compile_meta_learning_experience(receipt, signature=signature, accepted_parent_sha=PARENT)
    data = portable.to_data()
    raw = json.dumps(data, sort_keys=True)

    assert data["schema_version"] == 2
    assert portable.adapter_type == "verified_meta_episode_v1"
    assert portable.canonical_roles == ("__r0", "__r1")
    assert portable.role_count == 2
    assert portable.trainable_parameter_count == 0
    assert portable.source_verifier_evidence_digest.startswith("r269.meta-verifier-evidence.")
    assert portable.source_authority_digest.startswith("r269.source-authority.")
    assert "r269_verified_meta_episode" in portable.claim_scope
    assert "terminal_verified" in portable.claim_scope
    assert "zero_false_accepts" in portable.claim_scope
    assert "source_left" not in raw
    assert "source_right" not in raw
    assert "task_id" not in raw
    assert "family_id" not in raw
    assert portable_experience_from_data(data) == portable


def test_compilation_is_invariant_to_surface_role_names_for_same_verified_semantics():
    sig_a, receipt_a = _accepted_episode(("x", "y"))
    sig_b, receipt_b = _accepted_episode(("north", "south"))

    a = compile_meta_learning_experience(receipt_a, signature=sig_a, accepted_parent_sha=PARENT)
    b = compile_meta_learning_experience(receipt_b, signature=sig_b, accepted_parent_sha=PARENT)

    assert a.canonical_expression == b.canonical_expression
    assert a.canonical_roles == b.canonical_roles
    assert a.source_receipt_digest == b.source_receipt_digest
    assert a.source_verifier_evidence_digest == b.source_verifier_evidence_digest
    assert a.source_authority_digest == b.source_authority_digest
    assert a.portable_digest == b.portable_digest


def test_compiler_rejects_unverified_or_internally_inconsistent_episode_receipts():
    signature, receipt = _accepted_episode(("x", "y"))

    bad = (
        replace(receipt, passed=False, reason="diagnostic_ambiguity"),
        replace(receipt, selected_expression=None),
        replace(receipt, physical_terminal_calls=0),
        replace(receipt, ledger=tuple(row for row in receipt.ledger if row.phase != "terminal")),
    )
    for forged in bad:
        with pytest.raises(ValueError):
            compile_meta_learning_experience(forged, signature=signature, accepted_parent_sha=PARENT)

    with pytest.raises(ValueError):
        compile_meta_learning_experience(receipt, signature=signature, accepted_parent_sha="0" * 40)


def test_compiler_reverifies_selected_expression_against_evidence_and_rejects_digest_tampering():
    signature, receipt = _accepted_episode(("x", "y"))

    forged_expression = replace(
        receipt,
        selected_expression=Binary("mul", Field("x"), Field("y")),
    )
    with pytest.raises(ValueError, match="evidence"):
        compile_meta_learning_experience(forged_expression, signature=signature, accepted_parent_sha=PARENT)

    forged_row = replace(receipt.ledger[0], observation_digest="0" * 64)
    forged_ledger = replace(receipt, ledger=(forged_row, *receipt.ledger[1:]))
    with pytest.raises(ValueError, match="digest"):
        compile_meta_learning_experience(forged_ledger, signature=signature, accepted_parent_sha=PARENT)


def test_verified_meta_prior_is_scoped_to_its_declared_complete_finite_domain():
    signature, receipt = _accepted_episode(("x", "y"))
    learned = compile_meta_learning_experience(receipt, signature=signature, accepted_parent_sha=PARENT)
    shifted = _signature(("p", "q"), domain=(-3, 0, 3, 5))

    matches = match_portable_experiences((learned,), shifted)
    assert len(matches) == 1
    assert matches[0].compatible is False
    assert matches[0].reason == "verified_meta_domain_mismatch"


def test_later_renamed_task_reuses_compiled_episode_with_strict_search_advantage():
    source_signature, source_receipt = _accepted_episode(("alpha", "beta"), "add")
    learned = compile_meta_learning_experience(
        source_receipt,
        signature=source_signature,
        accepted_parent_sha=PARENT,
    )

    target_names = ("p", "q")
    target_signature = _signature(target_names)
    diagnostics, terminal = _contexts(target_names)
    oracle = lambda row: row["p"] - row["q"]

    transfer = run_meta_learning_episode((learned,), target_signature, diagnostics, terminal, oracle, _config())
    cold = run_cold_scratch(target_signature, diagnostics, terminal, oracle, _config())

    assert transfer.passed is True
    assert transfer.mode == "transfer"
    assert transfer.selected_prior_digest == learned.portable_digest
    assert cold.passed is True
    assert transfer.physical_diagnostic_calls <= cold.physical_diagnostic_calls
    assert transfer.transfer_candidates_considered < cold.scratch_candidates_considered
    assert (
        transfer.physical_diagnostic_calls < cold.physical_diagnostic_calls
        or transfer.transfer_candidates_considered < cold.scratch_candidates_considered
    )
    assert transfer.false_accepts == cold.false_accepts == 0


def test_sequential_chain_can_compile_an_accepted_transfer_and_reuse_it_after_restart():
    source_signature, source_receipt = _accepted_episode(("a", "b"), "add")
    prior1 = compile_meta_learning_experience(source_receipt, signature=source_signature, accepted_parent_sha=PARENT)

    middle_names = ("left", "right")
    middle_signature = _signature(middle_names)
    middle_diagnostics, middle_terminal = _contexts(middle_names)
    middle_oracle = lambda row: row["left"] - row["right"]
    middle = run_meta_learning_episode(
        (prior1,), middle_signature, middle_diagnostics, middle_terminal, middle_oracle, _config()
    )
    assert middle.passed is True
    assert middle.mode == "transfer"

    prior2 = compile_meta_learning_experience(middle, signature=middle_signature, accepted_parent_sha=PARENT)
    restarted = portable_experience_from_data(json.loads(json.dumps(prior2.to_data())))

    final_names = ("north", "south")
    final_signature = _signature(final_names)
    final_diagnostics, final_terminal = _contexts(final_names)
    final_oracle = lambda row: row["north"] - row["south"]
    transfer = run_meta_learning_episode(
        (restarted,), final_signature, final_diagnostics, final_terminal, final_oracle, _config()
    )
    cold = run_cold_scratch(final_signature, final_diagnostics, final_terminal, final_oracle, _config())

    assert transfer.passed is True
    assert transfer.mode == "transfer"
    assert transfer.selected_prior_digest == restarted.portable_digest
    assert transfer.false_accepts == 0
    assert cold.passed is True
    assert transfer.physical_diagnostic_calls <= cold.physical_diagnostic_calls
    assert transfer.transfer_candidates_considered < cold.scratch_candidates_considered
