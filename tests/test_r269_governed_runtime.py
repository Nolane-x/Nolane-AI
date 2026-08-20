from __future__ import annotations

import hashlib

import pytest

from cogcoder.r269_experience_compiler import compile_meta_learning_experience
from cogcoder.r269_governed_runtime import run_governed_meta_learning_episode
from cogcoder.r269_meta_learning_kernel import MetaLearningConfig, PublicTaskSignature, run_cold_scratch
from cogcoder.r269_promotion_authority import (
    AuthorityBoundPromotionRegistry,
    HostedVerifierAttestation,
    PromotionEvidenceAuthority,
)
from cogcoder.r269_scoped_promotion import (
    ChampionChallengerEvidence,
    PromotionCandidate,
    ScopedPromotionController,
    ScopedPromotionRegistry,
)

PARENT = 'fda7f502185266fedb00886d5786c6d28cc0e0eb'
DOMAIN = (-2, 0, 3, 5)
OPS = ('add', 'sub', 'mul', 'min', 'max')
VERIFIER_AUTHORITY = hashlib.sha256(b'r269-governed-hosted-authority').hexdigest()
VERIFIER_ISSUER = 'github.hosted.r269.promotion-verifier'


def _signature(names: tuple[str, str]) -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=names,
        numeric_domain='finite_integer',
        allowed_binary_ops=OPS,
        query_space_digest='r269.governed.complete-domain.v1',
        budget_contract='diagnostic<=4;candidate<=256',
        finite_integer_values=DOMAIN,
    )


def _contexts(names: tuple[str, str]):
    a, b = names
    rows = (
        {a: -2, b: 3}, {a: 0, b: 5}, {a: 3, b: -2},
        {a: 5, b: 0}, {a: 3, b: 5}, {a: -2, b: 0},
    )
    return rows[:4], rows[4:]


def _config() -> MetaLearningConfig:
    return MetaLearningConfig(
        max_diagnostic_queries=4,
        transfer_candidate_cap=64,
        scratch_candidate_cap=256,
        scratch_max_depth=1,
        min_scratch_partitions=2,
    )


def _learned_prior():
    signature = _signature(('source_left', 'source_right'))
    diagnostics, terminal = _contexts(signature.role_names)
    receipt = run_cold_scratch(
        signature, diagnostics, terminal,
        lambda row: row['source_left'] + row['source_right'], _config(),
    )
    assert receipt.passed is True
    learned = compile_meta_learning_experience(
        receipt, signature=signature, accepted_parent_sha=PARENT,
    )
    assert learned.adapter_type == 'verified_meta_episode_v1'
    return learned


def _evidence(candidate: PromotionCandidate, suffix: str = 'governed') -> ChampionChallengerEvidence:
    return ChampionChallengerEvidence(
        candidate_artifact_digest=candidate.artifact_digest,
        freeze_receipt_digest=candidate.freeze_receipt_digest,
        preregistered_scope_digest=candidate.structural_class_digest,
        champion_receipt_digest=f'receipt.champion.{suffix}',
        challenger_receipt_digest=f'receipt.challenger.{suffix}',
        terminal_verifier_digest=f'verifier.terminal.{suffix}',
        candidate_issuer=f'issuer.candidate.{suffix}',
        verifier_issuer=VERIFIER_ISSUER,
        verifier_authority_digest=VERIFIER_AUTHORITY,
        heldout_targets=8,
        champion_accepted_targets=8,
        challenger_accepted_targets=7,
        oracle_call_advantage=1,
        search_work_advantage=12,
        protected_regression_failures=0,
        false_accepts=0,
        budget_accounting_exact=True,
        terminal_verification_passed=True,
        target_answer_channel_detected=False,
    )


def _activate(learned, target_signature: PublicTaskSignature):
    candidate = PromotionCandidate(
        candidate_kind='portable_prior',
        artifact_digest=learned.portable_digest,
        structural_class_digest=target_signature.structural_class_digest,
        freeze_receipt_digest='freeze.' + learned.portable_digest,
        rollback_identity='rollback.' + learned.portable_digest,
        trainable_parameter_count=0,
    )
    evidence = _evidence(candidate)
    attestation = HostedVerifierAttestation.create(
        evidence=evidence,
        candidate=candidate,
        authority_root_digest=VERIFIER_AUTHORITY,
        verifier_issuer=VERIFIER_ISSUER,
        hosted_run_identity='github-actions:r269-governed:fixture',
        source_tree_digest=hashlib.sha256(b'r269-governed-exact-source-tree').hexdigest(),
    )
    envelope = PromotionEvidenceAuthority(
        VERIFIER_AUTHORITY, VERIFIER_ISSUER
    ).adjudicate(candidate, evidence, attestation)
    assert envelope.decision.promoted is True
    registry = AuthorityBoundPromotionRegistry(VERIFIER_AUTHORITY)
    registry.activate_verified(envelope)
    return registry, envelope.decision


def test_learned_meta_prior_cannot_influence_release_runtime_before_scoped_promotion():
    learned = _learned_prior()
    signature = _signature(('left', 'right'))
    diagnostics, terminal = _contexts(signature.role_names)
    with pytest.raises(ValueError, match='authority-bound scoped promotion'):
        run_governed_meta_learning_episode(
            (learned,), signature, diagnostics, terminal,
            lambda row: row['left'] - row['right'], _config(),
        )


def test_plain_caller_constructed_promotion_registry_is_not_release_authority():
    learned = _learned_prior()
    signature = _signature(('left', 'right'))
    diagnostics, terminal = _contexts(signature.role_names)
    candidate = PromotionCandidate(
        candidate_kind='portable_prior',
        artifact_digest=learned.portable_digest,
        structural_class_digest=signature.structural_class_digest,
        freeze_receipt_digest='freeze.plain',
        rollback_identity='rollback.plain',
        trainable_parameter_count=0,
    )
    decision = ScopedPromotionController(
        trusted_verifier_authority_digests=frozenset({VERIFIER_AUTHORITY})
    ).adjudicate(candidate, _evidence(candidate, 'plain'))
    plain = ScopedPromotionRegistry()
    plain.activate(decision)
    with pytest.raises(TypeError, match='AuthorityBoundPromotionRegistry'):
        run_governed_meta_learning_episode(
            (learned,), signature, diagnostics, terminal,
            lambda row: row['left'] - row['right'], _config(),
            promotion_registry=plain,
        )


def test_active_exact_scope_artifact_and_hosted_authority_authorizes_learned_transfer():
    learned = _learned_prior()
    signature = _signature(('left', 'right'))
    diagnostics, terminal = _contexts(signature.role_names)
    promotions, decision = _activate(learned, signature)
    receipt = run_governed_meta_learning_episode(
        (learned,), signature, diagnostics, terminal,
        lambda row: row['left'] - row['right'], _config(),
        promotion_registry=promotions,
    )
    assert receipt.passed is True
    assert receipt.mode == 'transfer'
    assert receipt.selected_prior_digest == learned.portable_digest
    assert receipt.false_accepts == 0
    assert promotions.active_for(signature.structural_class_digest) == decision
    assert promotions.is_authorized(
        signature.structural_class_digest,
        decision_digest=decision.decision_digest,
        artifact_digest=learned.portable_digest,
    )
    assert promotions.audit() is True


def test_exact_rollback_immediately_revokes_learned_prior_authority():
    learned = _learned_prior()
    signature = _signature(('left', 'right'))
    diagnostics, terminal = _contexts(signature.role_names)
    promotions, decision = _activate(learned, signature)
    promotions.rollback(
        signature.structural_class_digest,
        rollback_identity=decision.rollback_identity,
        expected_decision_digest=decision.decision_digest,
    )
    assert promotions.active_for(signature.structural_class_digest) is None
    assert promotions.audit() is True
    with pytest.raises(ValueError, match='authority-bound scoped promotion'):
        run_governed_meta_learning_episode(
            (learned,), signature, diagnostics, terminal,
            lambda row: row['left'] - row['right'], _config(),
            promotion_registry=promotions,
        )


def test_foreign_promoted_artifact_cannot_authorize_another_learned_prior():
    learned = _learned_prior()
    signature = _signature(('left', 'right'))
    diagnostics, terminal = _contexts(signature.role_names)
    foreign = PromotionCandidate(
        candidate_kind='portable_prior',
        artifact_digest='portable.foreign',
        structural_class_digest=signature.structural_class_digest,
        freeze_receipt_digest='freeze.foreign',
        rollback_identity='rollback.foreign',
        trainable_parameter_count=0,
    )
    evidence = _evidence(foreign, 'foreign')
    attestation = HostedVerifierAttestation.create(
        evidence=evidence,
        candidate=foreign,
        authority_root_digest=VERIFIER_AUTHORITY,
        verifier_issuer=VERIFIER_ISSUER,
        hosted_run_identity='github-actions:r269-governed:foreign-fixture',
        source_tree_digest=hashlib.sha256(b'r269-governed-foreign-source-tree').hexdigest(),
    )
    envelope = PromotionEvidenceAuthority(
        VERIFIER_AUTHORITY, VERIFIER_ISSUER
    ).adjudicate(foreign, evidence, attestation)
    promotions = AuthorityBoundPromotionRegistry(VERIFIER_AUTHORITY)
    promotions.activate_verified(envelope)
    with pytest.raises(ValueError, match='artifact does not match'):
        run_governed_meta_learning_episode(
            (learned,), signature, diagnostics, terminal,
            lambda row: row['left'] - row['right'], _config(),
            promotion_registry=promotions,
        )
