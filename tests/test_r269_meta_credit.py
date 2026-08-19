from __future__ import annotations

import pytest

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    CapabilityGapLedger,
    MetaCreditLedger,
    MetaLearningReceipt,
    PriorRegistry,
    PublicTaskSignature,
    adjudicate_prior_credit,
    record_capability_gap,
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
        receipt, source_authority_digest="authority.source", accepted_parent_sha=PARENT,
    )


def _signature():
    return PublicTaskSignature(
        role_names=("x", "y"), numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul"), query_space_digest="meta.q",
        budget_contract="diagnostic<=5;candidate<=256",
    )


def _receipt(*, passed=True, mode="transfer", diagnostic=1, transfer_work=8, scratch_work=120, prior=None):
    return MetaLearningReceipt(
        passed=passed, mode=mode,
        selected_expression=Binary("add", Field("x"), Field("y")) if passed else None,
        selected_prior_digest=prior.portable_digest if prior is not None and mode == "transfer" else None,
        physical_diagnostic_calls=diagnostic, physical_terminal_calls=2 if passed else 0,
        transfer_candidates_considered=transfer_work, scratch_candidates_considered=scratch_work,
        reused_observations=0, avoided_duplicate_calls=0, transfer_contradictions=0,
        quarantine_action=False, false_accepts=0,
        reason="accepted_transfer" if passed else "diagnostic_ambiguity",
        ledger=(), trainable_parameter_count=0,
    )


def test_credit_requires_terminal_acceptance_and_ablation_loss_of_advantage():
    prior = _prior(); registry = PriorRegistry(); ledger = MetaCreditLedger()
    accepted = _receipt(prior=prior, diagnostic=1, transfer_work=8)
    losing_ablation = _receipt(prior=None, mode="scratch", diagnostic=4, transfer_work=0, scratch_work=120)
    record = adjudicate_prior_credit(
        prior=prior, signature=_signature(), accepted_receipt=accepted,
        ablation_receipt=losing_ablation, registry=registry, credit_ledger=ledger,
        rollback_identity="rollback.prior.v1", evidence_digests=("verifier.run.1",),
    )
    assert record.credited is True
    assert record.oracle_call_advantage == 3
    assert record.search_work_advantage == 112
    assert registry.state_for(prior.portable_digest).positive_credit == 1

    denied = adjudicate_prior_credit(
        prior=prior, signature=_signature(), accepted_receipt=_receipt(passed=False, prior=prior),
        ablation_receipt=losing_ablation, registry=registry, credit_ledger=ledger,
        rollback_identity="rollback.prior.v1", evidence_digests=("verifier.run.2",),
    )
    assert denied.credited is False
    assert denied.reason == "target_not_accepted"


def test_credit_denied_when_ablation_keeps_same_advantage():
    prior = _prior(); registry = PriorRegistry(); ledger = MetaCreditLedger()
    accepted = _receipt(prior=prior, diagnostic=1, transfer_work=8)
    same = _receipt(prior=None, mode="scratch", diagnostic=1, transfer_work=0, scratch_work=8)
    record = adjudicate_prior_credit(
        prior=prior, signature=_signature(), accepted_receipt=accepted,
        ablation_receipt=same, registry=registry, credit_ledger=ledger,
        rollback_identity="rollback.prior.v1", evidence_digests=("verifier.run.3",),
    )
    assert record.credited is False
    assert record.reason == "ablation_retains_advantage"
    assert registry.state_for(prior.portable_digest).positive_credit == 0


def test_capability_gap_is_typed_identity_free_and_content_addressed():
    ledger = CapabilityGapLedger()
    first = record_capability_gap(
        ledger=ledger, gap_type="search_budget_gap", signature=_signature(),
        failure_receipt_digests=("receipt.failure.1", "receipt.failure.2"),
        falsified_prior_digests=("prior.dead",), observation_cost=4, search_cost=256,
        required_evidence="matched heldout improvement under the same hard budget",
    )
    second = record_capability_gap(
        ledger=ledger, gap_type="search_budget_gap", signature=_signature(),
        failure_receipt_digests=("receipt.failure.2", "receipt.failure.1"),
        falsified_prior_digests=("prior.dead",), observation_cost=4, search_cost=256,
        required_evidence="matched heldout improvement under the same hard budget",
    )
    assert first.gap_digest == second.gap_digest
    assert ledger.recurrence_count(first.gap_digest) == 2
    assert "task_id" not in first.__dataclass_fields__
    assert "family_id" not in first.__dataclass_fields__
    assert "target_output" not in first.__dataclass_fields__

    with pytest.raises(ValueError):
        record_capability_gap(
            ledger=ledger, gap_type="made_up_gap", signature=_signature(),
            failure_receipt_digests=("receipt.failure.3",), falsified_prior_digests=(),
            observation_cost=1, search_cost=1, required_evidence="fresh verifier evidence",
        )
