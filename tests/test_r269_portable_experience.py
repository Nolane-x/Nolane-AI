from __future__ import annotations

import json

import pytest

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import (
    PortableExperience,
    compile_r268_experience,
    portable_experience_from_data,
)


PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"


def _accepted_receipt(*, passed: bool = True, minimal: bool = True, proof_complete: bool = True):
    structure = AdaptiveCausalBasisStructureReceipt(
        passed=passed,
        selected=None,
        selected_basis_size=2,
        globally_minimal=minimal,
        necessity_certificates=(),
        unresolved_lower_order=(),
        legal_interventions=2,
        semantic_profiles=2,
        intervention_candidates_considered=2,
        bases_considered=1,
        composition_candidates_considered=7,
        oracle_calls=12,
        false_accepts=0,
        reason="adaptive_basis_discovered" if passed else "no_adaptive_basis",
        lower_basis_count=0,
        lower_basis_certified=0,
        lower_basis_inconclusive=0,
        lower_basis_universe_digest="lower.digest",
        proof_ledger_complete=proof_complete,
        lower_basis_certificates=(),
        trainable_parameter_count=0,
    )
    return AdaptiveCausalBasisReceipt(
        passed=passed,
        structure=structure,
        expression=Binary("add", Field("source_alpha"), Field("source_beta")),
        probe_expressions=(),
        probe_candidates_considered=(),
        probe_validation_cases=4,
        probe_validation_exact=4 if passed else 0,
        final_validation_cases=6,
        final_validation_exact=6 if passed else 0,
        reason="verified_adaptive_basis" if passed else "failed",
        selected_basis_size=2,
        globally_minimal=minimal,
        false_accepts=0,
        trainable_parameter_count=0,
        oracle_calls_total=22,
        terminal_probe_validation_cases=0,
        terminal_probe_validation_exact=0,
    )


def test_compile_r268_experience_is_identity_free_and_roundtrips():
    portable = compile_r268_experience(
        _accepted_receipt(),
        verifier_evidence_digest="verifier.fixture.authority.123",
        accepted_parent_sha=PARENT,
    )
    data = portable.to_data()
    raw = json.dumps(data, sort_keys=True)

    assert portable.adapter_type == "causal_basis_v1"
    assert portable.canonical_roles == ("__r0", "__r1")
    assert portable.trainable_parameter_count == 0
    assert "source_alpha" not in raw
    assert "source_beta" not in raw
    assert "task_id" not in raw
    assert "family_id" not in raw
    assert "target" not in raw.lower()
    assert portable_experience_from_data(data) == portable


@pytest.mark.parametrize(
    "receipt",
    [
        _accepted_receipt(passed=False),
        _accepted_receipt(minimal=False),
        _accepted_receipt(proof_complete=False),
    ],
)
def test_compile_requires_verified_minimal_proof_complete_r268(receipt):
    with pytest.raises(ValueError):
        compile_r268_experience(
            receipt,
            verifier_evidence_digest="verifier.fixture.authority.123",
            accepted_parent_sha=PARENT,
        )


def test_direct_construction_cannot_forge_digest_roles_or_parameter_count():
    portable = compile_r268_experience(
        _accepted_receipt(),
        verifier_evidence_digest="verifier.fixture.authority.123",
        accepted_parent_sha=PARENT,
    )

    with pytest.raises(ValueError):
        PortableExperience(
            adapter_type=portable.adapter_type,
            canonical_expression=portable.canonical_expression,
            canonical_roles=portable.canonical_roles,
            role_count=portable.role_count,
            source_receipt_digest=portable.source_receipt_digest,
            source_verifier_evidence_digest=portable.source_verifier_evidence_digest,
            source_authority_digest=portable.source_authority_digest,
            accepted_parent_sha=portable.accepted_parent_sha,
            claim_scope=portable.claim_scope,
            allowed_adaptation_ops=portable.allowed_adaptation_ops,
            portable_digest="forged",
            trainable_parameter_count=0,
        )

    with pytest.raises(ValueError):
        PortableExperience(
            adapter_type=portable.adapter_type,
            canonical_expression=portable.canonical_expression,
            canonical_roles=("source_alpha", "source_beta"),
            role_count=2,
            source_receipt_digest=portable.source_receipt_digest,
            source_verifier_evidence_digest=portable.source_verifier_evidence_digest,
            source_authority_digest=portable.source_authority_digest,
            accepted_parent_sha=portable.accepted_parent_sha,
            claim_scope=portable.claim_scope,
            allowed_adaptation_ops=portable.allowed_adaptation_ops,
            portable_digest=portable.portable_digest,
            trainable_parameter_count=0,
        )

    with pytest.raises(ValueError):
        PortableExperience(
            adapter_type=portable.adapter_type,
            canonical_expression=portable.canonical_expression,
            canonical_roles=portable.canonical_roles,
            role_count=portable.role_count,
            source_receipt_digest=portable.source_receipt_digest,
            source_verifier_evidence_digest=portable.source_verifier_evidence_digest,
            source_authority_digest=portable.source_authority_digest,
            accepted_parent_sha=portable.accepted_parent_sha,
            claim_scope=portable.claim_scope,
            allowed_adaptation_ops=portable.allowed_adaptation_ops,
            portable_digest=portable.portable_digest,
            trainable_parameter_count=1,
        )
