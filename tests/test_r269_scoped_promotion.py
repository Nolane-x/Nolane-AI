from __future__ import annotations

import importlib
import importlib.util

import pytest


MODULE = "cogcoder.r269_scoped_promotion"
SCOPE = "4f5a56f01b9b9d4b57fe7f0e196f48c3cb0f8f088ee409160840ba8ab58f1db8"
OTHER_SCOPE = "71cd4002f92c4a4668c0b6dbc914a4dac25cba00d91cde8490c93232eaa042b1"
VERIFIER_AUTHORITY = "1f" * 32


def _api():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, "R2.69 scoped promotion production module is missing"
    module = importlib.import_module(MODULE)
    return (
        module.PromotionCandidate,
        module.ChampionChallengerEvidence,
        module.ScopedPromotionController,
        module.PromotionDecision,
    )


def _controller():
    *_, ScopedPromotionController, _ = _api()
    return ScopedPromotionController(
        trusted_verifier_authority_digests=frozenset({VERIFIER_AUTHORITY})
    )


def _candidate(*, scope: str = SCOPE):
    PromotionCandidate, *_ = _api()
    return PromotionCandidate(
        candidate_kind="portable_prior",
        artifact_digest="artifact.r269.prior.abc123",
        structural_class_digest=scope,
        freeze_receipt_digest="freeze.r269.001",
        rollback_identity="rollback.r269.prior.001",
        trainable_parameter_count=0,
    )


def _evidence(candidate=None, **overrides):
    _, ChampionChallengerEvidence, *_ = _api()
    candidate = candidate or _candidate()
    values = dict(
        candidate_artifact_digest=candidate.artifact_digest,
        freeze_receipt_digest=candidate.freeze_receipt_digest,
        preregistered_scope_digest=candidate.structural_class_digest,
        champion_receipt_digest="receipt.champion.001",
        challenger_receipt_digest="receipt.challenger.001",
        terminal_verifier_digest="verifier.terminal.001",
        candidate_issuer="issuer.candidate",
        verifier_issuer="issuer.independent",
        verifier_authority_digest=VERIFIER_AUTHORITY,
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
    values.update(overrides)
    return ChampionChallengerEvidence(**values)


def test_scoped_promotion_requires_complete_independent_champion_challenger_evidence():
    candidate = _candidate()
    evidence = _evidence(candidate)

    first = _controller().adjudicate(candidate, evidence)
    replay = _controller().adjudicate(candidate, evidence)

    assert first == replay
    assert first.promoted is True
    assert first.reason == "scoped_promotion_accepted"
    assert first.structural_class_digest == SCOPE
    assert first.freeze_receipt_digest == candidate.freeze_receipt_digest
    assert first.rollback_identity == candidate.rollback_identity
    assert first.decision_digest.startswith("r269.promotion-decision.")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"freeze_receipt_digest": "freeze.r269.tampered"}, "freeze_receipt_mismatch"),
        ({"preregistered_scope_digest": OTHER_SCOPE}, "scope_mismatch"),
        ({"verifier_issuer": "issuer.candidate"}, "independent_verifier_required"),
        ({"oracle_call_advantage": 0, "search_work_advantage": 0, "champion_accepted_targets": 7}, "challenger_advantage_not_proven"),
        ({"protected_regression_failures": 1}, "protected_regression_loss"),
        ({"budget_accounting_exact": False}, "budget_accounting_inexact"),
        ({"terminal_verification_passed": False}, "terminal_verification_missing"),
        ({"target_answer_channel_detected": True}, "target_answer_channel_detected"),
        ({"false_accepts": 1}, "false_accepts_present"),
    ],
)
def test_promotion_fails_closed_on_each_authority_boundary(overrides, reason):
    candidate = _candidate()
    decision = _controller().adjudicate(candidate, _evidence(candidate, **overrides))
    assert decision.promoted is False
    assert decision.reason == reason


def test_scope_is_structural_and_cannot_be_global_or_rebound_after_evidence():
    PromotionCandidate, *_ = _api()
    with pytest.raises(ValueError, match="structural_class_digest"):
        PromotionCandidate(
            candidate_kind="portable_prior",
            artifact_digest="artifact.r269.prior.global",
            structural_class_digest="global",
            freeze_receipt_digest="freeze.r269.global",
            rollback_identity="rollback.r269.global",
            trainable_parameter_count=0,
        )

    candidate = _candidate()
    rebound = _evidence(candidate, preregistered_scope_digest=OTHER_SCOPE)
    decision = _controller().adjudicate(candidate, rebound)
    assert decision.promoted is False
    assert decision.reason == "scope_mismatch"


def test_decision_identity_changes_when_exact_freeze_receipt_changes():
    first_candidate = _candidate()
    PromotionCandidate, *_ = _api()
    second_candidate = PromotionCandidate(
        candidate_kind=first_candidate.candidate_kind,
        artifact_digest=first_candidate.artifact_digest,
        structural_class_digest=first_candidate.structural_class_digest,
        freeze_receipt_digest="freeze.r269.002",
        rollback_identity=first_candidate.rollback_identity,
        trainable_parameter_count=0,
    )
    first = _controller().adjudicate(first_candidate, _evidence(first_candidate))
    second = _controller().adjudicate(second_candidate, _evidence(second_candidate))
    assert first.promoted is second.promoted is True
    assert first.decision_digest != second.decision_digest
    assert first.evidence_digest != second.evidence_digest


def test_direct_decision_construction_rechecks_content_digest_and_rollback_binding():
    *_, PromotionDecision = _api()
    candidate = _candidate()
    decision = _controller().adjudicate(candidate, _evidence(candidate))

    with pytest.raises(ValueError, match="decision_digest"):
        PromotionDecision(
            promoted=decision.promoted,
            candidate_kind=decision.candidate_kind,
            candidate_artifact_digest=decision.candidate_artifact_digest,
            freeze_receipt_digest=decision.freeze_receipt_digest,
            structural_class_digest=decision.structural_class_digest,
            rollback_identity=decision.rollback_identity,
            evidence_digest=decision.evidence_digest,
            reason=decision.reason,
            decision_digest="forged",
            trainable_parameter_count=0,
        )

    with pytest.raises(ValueError):
        PromotionDecision(
            promoted=decision.promoted,
            candidate_kind=decision.candidate_kind,
            candidate_artifact_digest=decision.candidate_artifact_digest,
            freeze_receipt_digest=decision.freeze_receipt_digest,
            structural_class_digest=decision.structural_class_digest,
            rollback_identity="rollback.tampered",
            evidence_digest=decision.evidence_digest,
            reason=decision.reason,
            decision_digest=decision.decision_digest,
            trainable_parameter_count=0,
        )
