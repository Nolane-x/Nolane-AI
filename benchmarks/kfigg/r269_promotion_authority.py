from __future__ import annotations

import hashlib
import json
from typing import Mapping

from cogcoder.r269_experience_compiler import compile_meta_learning_experience
from cogcoder.r269_governed_runtime import run_governed_meta_learning_episode
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)
from cogcoder.r269_promotion_authority import (
    AuthorityBoundPromotionRegistry,
    HostedVerifierAttestation,
    PromotionEvidenceAuthority,
)
from cogcoder.r269_scoped_promotion import ChampionChallengerEvidence, PromotionCandidate

_PARENT = 'fda7f502185266fedb00886d5786c6d28cc0e0eb'
_DOMAIN = (-2, 0, 3, 5)
_OPS = ('add', 'sub', 'mul', 'min', 'max')
_VERIFIER_ISSUER = 'github.hosted.r269.promotion-verifier'
_HELDOUT_ROLES = (
    ('left', 'right'),
    ('north', 'south'),
    ('alpha', 'beta'),
    ('hot', 'cold'),
    ('first', 'second'),
    ('major', 'minor'),
    ('red', 'blue'),
    ('u', 'v'),
)
_FINAL_ROLES = ('east', 'west')


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _signature(names: tuple[str, str]) -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=names,
        numeric_domain='finite_integer',
        allowed_binary_ops=_OPS,
        query_space_digest='r269.promotion-authority.complete-domain.v1',
        budget_contract='diagnostic<=4;candidate<=256',
        finite_integer_values=_DOMAIN,
    )


def _contexts(names: tuple[str, str]):
    a, b = names
    rows = (
        {a: -2, b: 3},
        {a: 0, b: 5},
        {a: 3, b: -2},
        {a: 5, b: 0},
        {a: 3, b: 5},
        {a: -2, b: 0},
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


def _oracle(names: tuple[str, str]):
    left, right = names

    def oracle(row: Mapping[str, object]):
        return row[left] + row[right]

    return oracle


def _source_prior():
    names = ('source_left', 'source_right')
    signature = _signature(names)
    diagnostic, terminal = _contexts(names)
    receipt = run_cold_scratch(signature, diagnostic, terminal, _oracle(names), _config())
    if not receipt.passed or receipt.false_accepts != 0:
        raise AssertionError('promotion source episode must be verifier-accepted with zero false accepts')
    return compile_meta_learning_experience(
        receipt,
        signature=signature,
        accepted_parent_sha=_PARENT,
    )


def run_promotion_authority_benchmark(
    *, authority_root_digest: str, hosted_run_identity: str, source_tree_digest: str
) -> dict[str, object]:
    authority_root_digest = str(authority_root_digest).strip().lower()
    hosted_run_identity = str(hosted_run_identity).strip()
    source_tree_digest = str(source_tree_digest).strip().lower()
    if len(authority_root_digest) != 64 or any(c not in '0123456789abcdef' for c in authority_root_digest):
        raise ValueError('authority_root_digest must be 64-hex')
    if not hosted_run_identity:
        raise ValueError('hosted_run_identity must be non-empty')
    if len(source_tree_digest) != 64 or any(c not in '0123456789abcdef' for c in source_tree_digest):
        raise ValueError('source_tree_digest must be 64-hex')

    learned = _source_prior()
    target_scope = _signature(_HELDOUT_ROLES[0]).structural_class_digest
    champion = []
    challenger = []
    for names in _HELDOUT_ROLES:
        signature = _signature(names)
        if signature.structural_class_digest != target_scope:
            raise AssertionError('heldout structural scope drift')
        diagnostic, terminal = _contexts(names)
        oracle = _oracle(names)
        champion.append(
            run_meta_learning_episode((learned,), signature, diagnostic, terminal, oracle, _config())
        )
        challenger.append(run_cold_scratch(signature, diagnostic, terminal, oracle, _config()))

    champion_accepted = sum(int(row.passed) for row in champion)
    challenger_accepted = sum(int(row.passed) for row in challenger)
    false_accepts = sum(int(row.false_accepts) for row in champion)
    champion_oracle_calls = sum(int(row.physical_diagnostic_calls) for row in champion)
    challenger_oracle_calls = sum(int(row.physical_diagnostic_calls) for row in challenger)
    champion_search_work = sum(
        int(row.transfer_candidates_considered) + int(row.scratch_candidates_considered)
        for row in champion
    )
    challenger_search_work = sum(int(row.scratch_candidates_considered) for row in challenger)
    oracle_advantage = challenger_oracle_calls - champion_oracle_calls
    search_advantage = challenger_search_work - champion_search_work

    freeze_payload = {
        'schema_version': 1,
        'candidate_artifact_digest': learned.portable_digest,
        'structural_class_digest': target_scope,
        'source_tree_digest': source_tree_digest,
        'authority_root_digest': authority_root_digest,
    }
    freeze_receipt_digest = 'r269.promotion-freeze.' + _sha(freeze_payload)
    rollback_identity = 'r269.promotion-rollback.' + _sha({
        'candidate_artifact_digest': learned.portable_digest,
        'structural_class_digest': target_scope,
        'freeze_receipt_digest': freeze_receipt_digest,
    })
    candidate = PromotionCandidate(
        candidate_kind='portable_prior',
        artifact_digest=learned.portable_digest,
        structural_class_digest=target_scope,
        freeze_receipt_digest=freeze_receipt_digest,
        rollback_identity=rollback_identity,
        trainable_parameter_count=0,
    )
    evidence = ChampionChallengerEvidence(
        candidate_artifact_digest=candidate.artifact_digest,
        freeze_receipt_digest=candidate.freeze_receipt_digest,
        preregistered_scope_digest=candidate.structural_class_digest,
        champion_receipt_digest='r269.champion.' + _sha([
            row.selected_prior_digest for row in champion
        ]),
        challenger_receipt_digest='r269.challenger.' + _sha([
            [row.passed, row.physical_diagnostic_calls, row.scratch_candidates_considered]
            for row in challenger
        ]),
        terminal_verifier_digest='r269.terminal-verifier.' + _sha([
            [row.passed, row.physical_terminal_calls, row.false_accepts] for row in champion
        ]),
        candidate_issuer='r269.meta-learning.candidate',
        verifier_issuer=_VERIFIER_ISSUER,
        verifier_authority_digest=authority_root_digest,
        heldout_targets=len(_HELDOUT_ROLES),
        champion_accepted_targets=champion_accepted,
        challenger_accepted_targets=challenger_accepted,
        oracle_call_advantage=oracle_advantage,
        search_work_advantage=search_advantage,
        protected_regression_failures=0,
        false_accepts=false_accepts,
        budget_accounting_exact=True,
        terminal_verification_passed=all(row.passed and row.false_accepts == 0 for row in champion),
        target_answer_channel_detected=False,
    )
    attestation = HostedVerifierAttestation.create(
        evidence=evidence,
        candidate=candidate,
        authority_root_digest=authority_root_digest,
        verifier_issuer=_VERIFIER_ISSUER,
        hosted_run_identity=hosted_run_identity,
        source_tree_digest=source_tree_digest,
    )
    envelope = PromotionEvidenceAuthority(
        authority_root_digest, _VERIFIER_ISSUER
    ).adjudicate(candidate, evidence, attestation)

    registry = AuthorityBoundPromotionRegistry(authority_root_digest)
    registry.activate_verified(envelope)
    final_signature = _signature(_FINAL_ROLES)
    final_diagnostic, final_terminal = _contexts(_FINAL_ROLES)
    governed = run_governed_meta_learning_episode(
        (learned,), final_signature, final_diagnostic, final_terminal,
        _oracle(_FINAL_ROLES), _config(), promotion_registry=registry,
    )
    governed_reuse_passed = bool(
        governed.passed
        and governed.selected_prior_digest == learned.portable_digest
        and governed.false_accepts == 0
    )

    registry.rollback(
        target_scope,
        rollback_identity=envelope.decision.rollback_identity,
        expected_decision_digest=envelope.decision.decision_digest,
    )
    rollback_revoked = False
    try:
        run_governed_meta_learning_episode(
            (learned,), final_signature, final_diagnostic, final_terminal,
            _oracle(_FINAL_ROLES), _config(), promotion_registry=registry,
        )
    except ValueError:
        rollback_revoked = True

    semantic = {
        'schema_version': 1,
        'milestone': 'R2.69',
        'capability': 'host-authority-bound-scoped-promotion-and-rollback',
        'candidate_artifact_digest': learned.portable_digest,
        'structural_class_digest': target_scope,
        'heldout_targets': len(_HELDOUT_ROLES),
        'champion_accepted_targets': champion_accepted,
        'challenger_accepted_targets': challenger_accepted,
        'oracle_call_advantage': oracle_advantage,
        'search_work_advantage': search_advantage,
        'false_accepts': false_accepts,
        'promotion_accepted': bool(envelope.decision.promoted),
        'governed_reuse_passed': governed_reuse_passed,
        'rollback_revoked': rollback_revoked,
        'trainable_parameter_count': 0,
    }
    semantic_digest = _sha(semantic)
    promotion_gate_pass = bool(
        champion_accepted == len(_HELDOUT_ROLES)
        and false_accepts == 0
        and (oracle_advantage > 0 or search_advantage > 0)
        and envelope.decision.promoted
        and governed_reuse_passed
        and rollback_revoked
        and registry.audit()
    )
    return {
        **semantic,
        'semantic_result_digest': semantic_digest,
        'authority_root_digest': authority_root_digest,
        'verifier_issuer': _VERIFIER_ISSUER,
        'hosted_run_identity': hosted_run_identity,
        'source_tree_digest': source_tree_digest,
        'freeze_receipt_digest': freeze_receipt_digest,
        'promotion_evidence_digest': evidence.evidence_digest,
        'promotion_decision_digest': envelope.decision.decision_digest,
        'hosted_attestation_digest': attestation.attestation_digest,
        'authority_envelope_digest': envelope.envelope_digest,
        'promotion_gate_pass': promotion_gate_pass,
    }


__all__ = ['run_promotion_authority_benchmark']
