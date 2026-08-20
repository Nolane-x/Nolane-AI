from __future__ import annotations

from dataclasses import replace

import pytest

from cogcoder.r269_scoped_promotion import (
    ChampionChallengerEvidence,
    PromotionCandidate,
    ScopedPromotionController,
    ScopedPromotionRegistry,
)

SCOPE = "4f5a56f01b9b9d4b57fe7f0e196f48c3cb0f8f088ee409160840ba8ab58f1db8"
TRUSTED_VERIFIER = "1f" * 32
UNTRUSTED_VERIFIER = "2e" * 32


def _candidate() -> PromotionCandidate:
    return PromotionCandidate(
        candidate_kind="portable_prior",
        artifact_digest="artifact.r269.authority-hardening",
        structural_class_digest=SCOPE,
        freeze_receipt_digest="freeze.r269.authority-hardening",
        rollback_identity="rollback.r269.authority-hardening",
        trainable_parameter_count=0,
    )


def _evidence(candidate: PromotionCandidate, authority: str) -> ChampionChallengerEvidence:
    return ChampionChallengerEvidence(
        candidate_artifact_digest=candidate.artifact_digest,
        freeze_receipt_digest=candidate.freeze_receipt_digest,
        preregistered_scope_digest=candidate.structural_class_digest,
        champion_receipt_digest="receipt.champion.authority-hardening",
        challenger_receipt_digest="receipt.challenger.authority-hardening",
        terminal_verifier_digest="verifier.terminal.authority-hardening",
        candidate_issuer="self-asserted-label-a",
        verifier_issuer="self-asserted-label-b",
        verifier_authority_digest=authority,
        heldout_targets=8,
        champion_accepted_targets=8,
        challenger_accepted_targets=7,
        oracle_call_advantage=3,
        search_work_advantage=41,
        protected_regression_failures=0,
        false_accepts=0,
        budget_accounting_exact=True,
        terminal_verification_passed=True,
        target_answer_channel_detected=False,
    )


def _controller() -> ScopedPromotionController:
    return ScopedPromotionController(
        trusted_verifier_authority_digests=frozenset({TRUSTED_VERIFIER})
    )


def test_free_form_issuer_label_separation_is_not_independent_verifier_authority():
    candidate = _candidate()
    decision = _controller().adjudicate(candidate, _evidence(candidate, UNTRUSTED_VERIFIER))
    assert decision.promoted is False
    assert decision.reason == "untrusted_verifier_authority"


def test_host_trusted_verifier_authority_is_evidence_bound_and_can_promote():
    candidate = _candidate()
    evidence = _evidence(candidate, TRUSTED_VERIFIER)
    decision = _controller().adjudicate(candidate, evidence)
    assert decision.promoted is True
    assert decision.reason == "scoped_promotion_accepted"

    tampered = replace(evidence, verifier_authority_digest=UNTRUSTED_VERIFIER)
    assert tampered.evidence_digest != evidence.evidence_digest
    denied = _controller().adjudicate(candidate, tampered)
    assert denied.promoted is False
    assert denied.reason == "untrusted_verifier_authority"


def test_default_controller_is_fail_closed_and_denied_decision_cannot_activate_registry():
    candidate = _candidate()
    decision = ScopedPromotionController().adjudicate(candidate, _evidence(candidate, TRUSTED_VERIFIER))
    assert decision.promoted is False
    assert decision.reason == "untrusted_verifier_authority"

    registry = ScopedPromotionRegistry()
    with pytest.raises(ValueError, match="promoted decision"):
        registry.activate(decision)
