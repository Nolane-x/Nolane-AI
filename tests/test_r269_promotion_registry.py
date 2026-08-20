from __future__ import annotations

import pytest

from cogcoder.r269_scoped_promotion import (
    ChampionChallengerEvidence,
    PromotionCandidate,
    ScopedPromotionController,
)

SCOPE = "4f5a56f01b9b9d4b57fe7f0e196f48c3cb0f8f088ee409160840ba8ab58f1db8"


def _decision(
    *,
    artifact="artifact.r269.prior.abc123",
    freeze="freeze.r269.001",
    rollback="rollback.r269.prior.001",
    promoted=True,
):
    candidate = PromotionCandidate(
        candidate_kind="portable_prior",
        artifact_digest=artifact,
        structural_class_digest=SCOPE,
        freeze_receipt_digest=freeze,
        rollback_identity=rollback,
        trainable_parameter_count=0,
    )
    evidence = ChampionChallengerEvidence(
        candidate_artifact_digest=candidate.artifact_digest,
        freeze_receipt_digest=candidate.freeze_receipt_digest,
        preregistered_scope_digest=candidate.structural_class_digest,
        champion_receipt_digest="receipt.champion." + artifact[-6:],
        challenger_receipt_digest="receipt.challenger." + artifact[-6:],
        terminal_verifier_digest="verifier.terminal.001",
        candidate_issuer="issuer.candidate",
        verifier_issuer="issuer.independent",
        heldout_targets=8,
        champion_accepted_targets=8 if promoted else 0,
        challenger_accepted_targets=7,
        oracle_call_advantage=3,
        search_work_advantage=41,
        protected_regression_failures=0,
        false_accepts=0,
        budget_accounting_exact=True,
        terminal_verification_passed=True,
        target_answer_channel_detected=False,
    )
    return ScopedPromotionController().adjudicate(candidate, evidence)


def test_registry_activates_one_scoped_decision_idempotently_and_records_history():
    from cogcoder.r269_scoped_promotion import ScopedPromotionRegistry

    registry = ScopedPromotionRegistry()
    decision = _decision()
    first = registry.activate(decision)
    replay = registry.activate(decision)

    assert first == replay
    assert registry.active_for(SCOPE) == decision
    assert len(registry.history) == 1
    assert first.action == "activate"
    assert first.event_digest.startswith("r269.promotion-event.")
    assert registry.audit() is True


def test_registry_rejects_denied_decision_and_silent_scope_replacement():
    from cogcoder.r269_scoped_promotion import ScopedPromotionRegistry

    registry = ScopedPromotionRegistry()
    denied = _decision(promoted=False)
    with pytest.raises(ValueError, match="promoted decision"):
        registry.activate(denied)

    first = _decision()
    second = _decision(
        artifact="artifact.r269.prior.second",
        freeze="freeze.r269.002",
        rollback="rollback.r269.prior.002",
    )
    registry.activate(first)
    with pytest.raises(ValueError, match="already has an active promotion"):
        registry.activate(second)
    assert registry.active_for(SCOPE) == first
    assert registry.audit() is True


def test_rollback_requires_exact_active_decision_and_rollback_identity_then_allows_replacement():
    from cogcoder.r269_scoped_promotion import ScopedPromotionRegistry

    registry = ScopedPromotionRegistry()
    first = _decision()
    second = _decision(
        artifact="artifact.r269.prior.second",
        freeze="freeze.r269.002",
        rollback="rollback.r269.prior.002",
    )
    registry.activate(first)

    with pytest.raises(ValueError, match="rollback_identity"):
        registry.rollback(
            SCOPE,
            rollback_identity="rollback.wrong",
            expected_decision_digest=first.decision_digest,
        )
    with pytest.raises(ValueError, match="expected_decision_digest"):
        registry.rollback(
            SCOPE,
            rollback_identity=first.rollback_identity,
            expected_decision_digest="r269.promotion-decision.stale",
        )
    assert registry.active_for(SCOPE) == first

    rolled = registry.rollback(
        SCOPE,
        rollback_identity=first.rollback_identity,
        expected_decision_digest=first.decision_digest,
    )
    assert rolled.action == "rollback"
    assert registry.active_for(SCOPE) is None

    activated = registry.activate(second)
    assert activated.action == "activate"
    assert registry.active_for(SCOPE) == second
    assert len(registry.history) == 3
    assert registry.audit() is True
