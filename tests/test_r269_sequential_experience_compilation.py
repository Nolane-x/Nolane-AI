from __future__ import annotations

import json
from dataclasses import replace

import pytest

from cogcoder.r269_experience_compiler import compile_meta_learning_experience
from cogcoder.r269_causal_basis_adapter import portable_experience_from_data
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"
DOMAIN = (-2, 0, 3, 5)


def _signature(names: tuple[str, str]) -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=names,
        numeric_domain="finite_integer",
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="r269.sequential.complete-domain.v1",
        budget_contract="diagnostic<=4;candidate<=256",
        finite_integer_values=DOMAIN,
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


def _accepted_add_episode(names: tuple[str, str] = ("x", "y")):
    signature = _signature(names)
    diagnostics, terminal = _contexts(names)
    a, b = names
    receipt = run_cold_scratch(
        signature,
        diagnostics,
        terminal,
        lambda row: row[a] + row[b],
        _config(),
    )
    assert receipt.passed is True
    assert receipt.mode == "scratch"
    assert receipt.physical_terminal_calls == len(terminal)
    return signature, receipt


def test_verified_target_episode_compiles_to_identity_free_roundtrippable_portable_experience():
    signature, receipt = _accepted_add_episode(("source_left", "source_right"))
    portable = compile_meta_learning_experience(
        receipt,
        signature=signature,
        accepted_parent_sha=PARENT,
    )
    raw = json.dumps(portable.to_data(), sort_keys=True)

    assert portable.adapter_type == "verified_meta_episode_v1"
    assert portable.canonical_roles == ("__r0", "__r1")
    assert portable.role_count == 2
    assert portable.trainable_parameter_count == 0
    assert "r269_verified_meta_episode" in portable.claim_scope
    assert "terminal_verified" in portable.claim_scope
    assert "zero_false_accepts" in portable.claim_scope
    assert "source_left" not in raw
    assert "source_right" not in raw
    assert "task_id" not in raw
    assert "family_id" not in raw
    assert portable_experience_from_data(portable.to_data()) == portable


def test_compilation_is_invariant_to_surface_role_names_for_same_verified_semantics():
    sig_a, receipt_a = _accepted_add_episode(("x", "y"))
    sig_b, receipt_b = _accepted_add_episode(("north", "south"))

    a = compile_meta_learning_experience(receipt_a, signature=sig_a, accepted_parent_sha=PARENT)
    b = compile_meta_learning_experience(receipt_b, signature=sig_b, accepted_parent_sha=PARENT)

    assert a.canonical_expression == b.canonical_expression
    assert a.canonical_roles == b.canonical_roles
    assert a.source_receipt_digest == b.source_receipt_digest
    assert a.source_authority_digest == b.source_authority_digest
    assert a.portable_digest == b.portable_digest


def test_compiler_rejects_unverified_or_internally_inconsistent_episode_receipts():
    signature, receipt = _accepted_add_episode()

    bad = (
        replace(receipt, passed=False, reason="diagnostic_ambiguity"),
        replace(receipt, selected_expression=None),
        replace(receipt, physical_terminal_calls=0),
        replace(receipt, ledger=tuple(row for row in receipt.ledger if row.phase != "terminal")),
    )
    for forged in bad:
        with pytest.raises(ValueError):
            compile_meta_learning_experience(
                forged,
                signature=signature,
                accepted_parent_sha=PARENT,
            )

    with pytest.raises(ValueError):
        compile_meta_learning_experience(
            receipt,
            signature=signature,
            accepted_parent_sha="0" * 40,
        )


def test_later_renamed_task_reuses_compiled_episode_with_less_fresh_evidence_than_cold_scratch():
    source_signature, source_receipt = _accepted_add_episode(("alpha", "beta"))
    learned = compile_meta_learning_experience(
        source_receipt,
        signature=source_signature,
        accepted_parent_sha=PARENT,
    )

    target_names = ("p", "q")
    target_signature = _signature(target_names)
    diagnostics, terminal = _contexts(target_names)
    oracle = lambda row: row["p"] - row["q"]

    transfer = run_meta_learning_episode(
        (learned,),
        target_signature,
        diagnostics,
        terminal,
        oracle,
        _config(),
    )
    cold = run_cold_scratch(
        target_signature,
        diagnostics,
        terminal,
        oracle,
        _config(),
    )

    assert transfer.passed is True
    assert transfer.mode == "transfer"
    assert transfer.selected_prior_digest == learned.portable_digest
    assert cold.passed is True
    assert transfer.physical_diagnostic_calls < cold.physical_diagnostic_calls
    assert transfer.transfer_candidates_considered < cold.scratch_candidates_considered
    assert transfer.false_accepts == cold.false_accepts == 0
