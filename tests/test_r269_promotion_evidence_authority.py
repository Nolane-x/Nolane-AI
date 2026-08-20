from __future__ import annotations

import hashlib

import pytest

from cogcoder.r269_promotion_authority import (
    AuthorityBoundPromotionRegistry,
    HostedVerifierAttestation,
    PromotionEvidenceAuthority,
)
from cogcoder.r269_scoped_promotion import ChampionChallengerEvidence, PromotionCandidate


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _candidate() -> PromotionCandidate:
    return PromotionCandidate(
        candidate_kind='portable_prior',
        artifact_digest='portable.authority.candidate',
        structural_class_digest=_hex('scope'),
        freeze_receipt_digest='freeze.authority.candidate',
        rollback_identity='rollback.authority.candidate',
        trainable_parameter_count=0,
    )


def _evidence(candidate: PromotionCandidate, *, root: str) -> ChampionChallengerEvidence:
    return ChampionChallengerEvidence(
        candidate_artifact_digest=candidate.artifact_digest,
        freeze_receipt_digest=candidate.freeze_receipt_digest,
        preregistered_scope_digest=candidate.structural_class_digest,
        champion_receipt_digest='receipt.champion.authority',
        challenger_receipt_digest='receipt.challenger.authority',
        terminal_verifier_digest='receipt.terminal.authority',
        candidate_issuer='candidate.agent',
        verifier_issuer='github.hosted.verifier',
        verifier_authority_digest=root,
        heldout_targets=8,
        champion_accepted_targets=8,
        challenger_accepted_targets=7,
        oracle_call_advantage=1,
        search_work_advantage=2,
        protected_regression_failures=0,
        false_accepts=0,
        budget_accounting_exact=True,
        terminal_verification_passed=True,
        target_answer_channel_detected=False,
    )


def _attestation(candidate: PromotionCandidate, evidence: ChampionChallengerEvidence, *, root: str):
    return HostedVerifierAttestation.create(
        evidence=evidence,
        candidate=candidate,
        authority_root_digest=root,
        verifier_issuer='github.hosted.verifier',
        hosted_run_identity='github-actions:run:32300000000:job:96300000000',
        source_tree_digest=_hex('exact-source-tree'),
    )


def test_caller_distinct_issuer_strings_are_not_release_authority_without_hosted_attestation():
    candidate = _candidate()
    root = _hex('trusted-root')
    evidence = _evidence(candidate, root=root)
    authority = PromotionEvidenceAuthority(
        authority_root_digest=root,
        verifier_issuer='github.hosted.verifier',
    )

    with pytest.raises(TypeError, match='HostedVerifierAttestation'):
        authority.adjudicate(candidate, evidence, None)


def test_attestation_is_content_addressed_to_evidence_candidate_scope_freeze_and_source_tree():
    candidate = _candidate()
    root = _hex('trusted-root')
    evidence = _evidence(candidate, root=root)
    receipt = _attestation(candidate, evidence, root=root)

    assert receipt.evidence_digest == evidence.evidence_digest
    assert receipt.candidate_artifact_digest == candidate.artifact_digest
    assert receipt.structural_class_digest == candidate.structural_class_digest
    assert receipt.freeze_receipt_digest == candidate.freeze_receipt_digest
    assert receipt.source_tree_digest == _hex('exact-source-tree')
    assert receipt.attestation_digest.startswith('r269.hosted-promotion-attestation.')


def test_wrong_authority_root_or_verifier_issuer_fails_closed():
    candidate = _candidate()
    trusted_root = _hex('trusted-root')
    untrusted_root = _hex('untrusted-root')
    evidence = _evidence(candidate, root=trusted_root)
    receipt = _attestation(candidate, evidence, root=untrusted_root)
    authority = PromotionEvidenceAuthority(
        authority_root_digest=trusted_root,
        verifier_issuer='github.hosted.verifier',
    )
    with pytest.raises(ValueError, match='authority root'):
        authority.adjudicate(candidate, evidence, receipt)

    trusted_receipt = _attestation(candidate, evidence, root=trusted_root)
    wrong_issuer = PromotionEvidenceAuthority(
        authority_root_digest=trusted_root,
        verifier_issuer='different.verifier',
    )
    with pytest.raises(ValueError, match='verifier issuer'):
        wrong_issuer.adjudicate(candidate, evidence, trusted_receipt)


def test_evidence_authority_digest_must_equal_attested_trusted_root():
    candidate = _candidate()
    trusted_root = _hex('trusted-root')
    forged_root = _hex('forged-root')
    evidence = _evidence(candidate, root=forged_root)
    receipt = _attestation(candidate, evidence, root=trusted_root)
    authority = PromotionEvidenceAuthority(trusted_root, 'github.hosted.verifier')

    with pytest.raises(ValueError, match='evidence verifier authority'):
        authority.adjudicate(candidate, evidence, receipt)


def test_only_authority_bound_envelope_can_activate_release_registry_and_rollback_revokes_it():
    candidate = _candidate()
    root = _hex('trusted-root')
    evidence = _evidence(candidate, root=root)
    receipt = _attestation(candidate, evidence, root=root)
    authority = PromotionEvidenceAuthority(root, 'github.hosted.verifier')
    envelope = authority.adjudicate(candidate, evidence, receipt)
    assert envelope.decision.promoted is True

    registry = AuthorityBoundPromotionRegistry(root)
    event = registry.activate_verified(envelope)
    assert event.action == 'activate'
    assert registry.is_authorized(
        candidate.structural_class_digest,
        decision_digest=envelope.decision.decision_digest,
        artifact_digest=candidate.artifact_digest,
    )

    with pytest.raises(TypeError, match='activate_verified'):
        registry.activate(envelope.decision)

    registry.rollback(
        candidate.structural_class_digest,
        rollback_identity=envelope.decision.rollback_identity,
        expected_decision_digest=envelope.decision.decision_digest,
    )
    assert not registry.is_authorized(
        candidate.structural_class_digest,
        decision_digest=envelope.decision.decision_digest,
        artifact_digest=candidate.artifact_digest,
    )
    assert registry.audit() is True
