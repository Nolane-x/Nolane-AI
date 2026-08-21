from __future__ import annotations

import pytest

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import (
    PortableExperience,
    VerifiedExperienceEnvelope,
    compile_r268_experience,
)

PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"


def _receipt(expr=None):
    expr = expr or Binary("add", Field("a"), Field("b"))
    structure = AdaptiveCausalBasisStructureReceipt(
        passed=True,
        selected=None,
        selected_basis_size=2,
        globally_minimal=True,
        necessity_certificates=(),
        unresolved_lower_order=(),
        legal_interventions=2,
        semantic_profiles=2,
        intervention_candidates_considered=2,
        bases_considered=1,
        composition_candidates_considered=4,
        oracle_calls=8,
        false_accepts=0,
        reason="adaptive_basis_discovered",
        lower_basis_count=0,
        lower_basis_certified=0,
        lower_basis_inconclusive=0,
        lower_basis_universe_digest="lower",
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
        probe_validation_cases=2,
        probe_validation_exact=2,
        final_validation_cases=4,
        final_validation_exact=4,
        reason="verified_adaptive_basis",
        selected_basis_size=2,
        globally_minimal=True,
        false_accepts=0,
        trainable_parameter_count=0,
        oracle_calls_total=14,
        terminal_probe_validation_cases=0,
        terminal_probe_validation_exact=0,
    )


def _compile(verifier="verifier.github.run.123"):
    return compile_r268_experience(
        _receipt(),
        verifier_evidence_digest=verifier,
        accepted_parent_sha=PARENT,
    )


def test_compiler_derives_authority_from_receipt_parent_and_verifier_evidence():
    first = _compile("verifier.github.run.123")
    replay = _compile("verifier.github.run.123")
    other_verifier = _compile("verifier.github.run.456")

    assert first == replay
    assert first.source_verifier_evidence_digest == "verifier.github.run.123"
    assert first.source_authority_digest.startswith("r269.source-authority.")
    assert first.source_authority_digest != other_verifier.source_authority_digest


def test_detached_envelope_authority_string_is_rejected():
    portable = _compile()
    with pytest.raises(ValueError, match="source_authority_digest"):
        VerifiedExperienceEnvelope(
            source_receipt_digest=portable.source_receipt_digest,
            source_verifier_evidence_digest=portable.source_verifier_evidence_digest,
            source_authority_digest="detached.authority.string",
            accepted_parent_sha=PARENT,
            claim_scope=portable.claim_scope,
            source_basis_size=2,
            trainable_parameter_count=0,
        )


def test_portable_direct_construction_rechecks_authority_binding():
    portable = _compile()
    with pytest.raises(ValueError, match="source_authority_digest"):
        PortableExperience(
            adapter_type=portable.adapter_type,
            canonical_expression=portable.canonical_expression,
            canonical_roles=portable.canonical_roles,
            role_count=portable.role_count,
            source_receipt_digest=portable.source_receipt_digest,
            source_verifier_evidence_digest="verifier.github.run.tampered",
            source_authority_digest=portable.source_authority_digest,
            accepted_parent_sha=portable.accepted_parent_sha,
            claim_scope=portable.claim_scope,
            allowed_adaptation_ops=portable.allowed_adaptation_ops,
            portable_digest=portable.portable_digest,
            trainable_parameter_count=0,
        )


def test_raw_unbound_authority_argument_is_not_a_supported_compile_channel():
    with pytest.raises(TypeError):
        compile_r268_experience(
            _receipt(),
            source_authority_digest="caller.chosen",
            accepted_parent_sha=PARENT,
        )
