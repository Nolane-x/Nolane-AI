from __future__ import annotations

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import PublicTaskSignature, match_portable_experiences

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"


def _receipt(expr, size):
    structure = AdaptiveCausalBasisStructureReceipt(
        passed=True, selected=None, selected_basis_size=size, globally_minimal=True,
        necessity_certificates=(), unresolved_lower_order=(), legal_interventions=size,
        semantic_profiles=size, intervention_candidates_considered=size, bases_considered=1,
        composition_candidates_considered=4, oracle_calls=8, false_accepts=0,
        reason="adaptive_basis_discovered", lower_basis_count=0, lower_basis_certified=0,
        lower_basis_inconclusive=0, lower_basis_universe_digest="lower", proof_ledger_complete=True,
        lower_basis_certificates=(), trainable_parameter_count=0,
    )
    return AdaptiveCausalBasisReceipt(
        passed=True, structure=structure, expression=expr, probe_expressions=(),
        probe_candidates_considered=(), probe_validation_cases=2, probe_validation_exact=2,
        final_validation_cases=4, final_validation_exact=4, reason="verified_adaptive_basis",
        selected_basis_size=size, globally_minimal=True, false_accepts=0,
        trainable_parameter_count=0, oracle_calls_total=14,
        terminal_probe_validation_cases=0, terminal_probe_validation_exact=0,
    )


def _prior(authority="authority.a"):
    return compile_r268_experience(
        _receipt(Binary("add", Field("a"), Field("b")), 2),
        source_authority_digest=authority,
        accepted_parent_sha=PARENT,
    )


def test_matching_is_insertion_order_invariant_and_identity_free():
    a = _prior("authority.a")
    b = _prior("authority.b")
    signature = PublicTaskSignature(
        role_names=("left", "right"), numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul"), query_space_digest="q.public",
        budget_contract="oracle<=8;candidate<=64",
    )
    forward = match_portable_experiences((a, b), signature)
    reverse = match_portable_experiences((b, a), signature)
    assert [row.portable.portable_digest for row in forward] == [row.portable.portable_digest for row in reverse]
    assert all(row.compatible for row in forward)


def test_incompatible_role_cardinality_is_rejected():
    prior = _prior()
    signature = PublicTaskSignature(
        role_names=("a", "b", "c"), numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul"), query_space_digest="q.public",
        budget_contract="oracle<=8;candidate<=64",
    )
    rows = match_portable_experiences((prior,), signature)
    assert len(rows) == 1
    assert rows[0].compatible is False
    assert rows[0].reason == "role_cardinality_mismatch"


def test_public_signature_has_no_task_or_family_identity_channel():
    fields = PublicTaskSignature.__dataclass_fields__
    assert "task_id" not in fields
    assert "task_name" not in fields
    assert "family_id" not in fields
    assert "benchmark_seed" not in fields
