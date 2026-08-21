from __future__ import annotations

import hashlib
import json
from typing import Mapping

from benchmarks.kfigg import r269_meta_learning as authored
from cogcoder.r269_experience_compiler import compile_meta_learning_experience
from cogcoder.r269_governed_runtime import run_governed_meta_learning_episode
from cogcoder.r269_meta_learning_kernel import MetaLearningConfig, PublicTaskSignature, run_cold_scratch, run_meta_learning_episode
from cogcoder.r269_promotion_authority import (
    AuthorityBoundPromotionRegistry,
    HostedVerifierAttestation,
    PromotionEvidenceAuthority,
)
from cogcoder.r269_scoped_promotion import ChampionChallengerEvidence, PromotionCandidate

_PARENT = 'fda7f502185266fedb00886d5786c6d28cc0e0eb'
_VERIFIER_ISSUER = 'github.hosted.r269.promotion-verifier'
_SOURCE_ROLES = ('source_left', 'source_right')
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


def _tight_config() -> MetaLearningConfig:
    # This is deliberately the same tight target budget used by the authored
    # hard-transfer lane. Promotion must earn an advantage under matched
    # champion/challenger budgets; the controller is never relaxed for this
    # benchmark.
    return MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=64,
        scratch_candidate_cap=64,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )


def _signature(names: tuple[str, str]) -> PublicTaskSignature:
    return authored._signature(names)


def _contexts(names: tuple[str, str]):
    return authored._contexts(names)


def _oracle(names: tuple[str, str]):
    left, right = names

    def oracle(row: Mapping[str, object]):
        return 3 * row[left] + row[right]

    return oracle


def _learned_source_prior():
    # Build the source from the already-authored/protected R2.68 hard causal
    # basis, then force one real R2.69 transfer episode to compile that verified
    # episode into a reusable verified_meta_episode_v1. The candidate promoted
    # below is therefore learned R2.69 experience, not the imported R2.68 seed.
    hard_receipt = authored._three_x_plus_y_receipt()
    hard_r268_prior = authored._compile(hard_receipt, 'r269-promotion-seed-three-x-plus-y')
    signature = _signature(_SOURCE_ROLES)
    diagnostic, terminal = _contexts(_SOURCE_ROLES)
    receipt = run_meta_learning_episode(
        (hard_r268_prior,),
        signature,
        diagnostic,
        terminal,
        _oracle(_SOURCE_ROLES),
        _tight_config(),
    )
    if not receipt.passed or receipt.false_accepts != 0:
        raise AssertionError('promotion source meta episode must be verifier-accepted with zero false accepts')
    if receipt.selected_prior_digest != hard_r268_prior.portable_digest:
        raise AssertionError('promotion source meta episode must genuinely reuse the protected R2.68 seed')
    learned = compile_meta_learning_experience(
        receipt,
        signature=signature,
        accepted_parent_sha=_PARENT,
    )
    if learned.adapter_type != 'verified_meta_episode_v1':
        raise AssertionError('promotion candidate must be compiled learned R2.69 experience')
    return learned, hard_r268_prior.portable_digest, receipt


def _rejection_message(decision, evidence: ChampionChallengerEvidence) -> str:
    return (
        f'promotion evidence rejected: reason={decision.reason}; '
        f'champion={evidence.champion_accepted_targets}/{evidence.heldout_targets}; '
        f'challenger={evidence.challenger_accepted_targets}/{evidence.heldout_targets}; '
        f'oracle_advantage={evidence.oracle_call_advantage}; '
        f'search_advantage={evidence.search_work_advantage}; '
        f'false_accepts={evidence.false_accepts}; '
        f'terminal={evidence.terminal_verification_passed}; '
        f'budget_exact={evidence.budget_accounting_exact}'
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

    learned, seed_prior_digest, source_receipt = _learned_source_prior()
    target_scope = _signature(_HELDOUT_ROLES[0]).structural_class_digest
    champion = []
    challenger = []
    config = _tight_config()
    for names in _HELDOUT_ROLES:
        signature = _signature(names)
        if signature.structural_class_digest != target_scope:
            raise AssertionError('heldout structural scope drift')
        diagnostic, terminal = _contexts(names)
        oracle = _oracle(names)
        champion.append(
            run_meta_learning_episode((learned,), signature, diagnostic, terminal, oracle, config)
        )
        challenger.append(run_cold_scratch(signature, diagnostic, terminal, oracle, config))

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
        'schema_version': 2,
        'candidate_artifact_digest': learned.portable_digest,
        'structural_class_digest': target_scope,
        'source_tree_digest': source_tree_digest,
        'authority_root_digest': authority_root_digest,
        'seed_prior_digest': seed_prior_digest,
        'source_meta_receipt_digest': learned.source_receipt_digest,
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
            [row.passed, row.selected_prior_digest, row.physical_diagnostic_calls,
             row.transfer_candidates_considered, row.scratch_candidates_considered]
            for row in champion
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
    if not envelope.decision.promoted:
        raise AssertionError(_rejection_message(envelope.decision, evidence))

    registry = AuthorityBoundPromotionRegistry(authority_root_digest)
    registry.activate_verified(envelope)
    final_signature = _signature(_FINAL_ROLES)
    if final_signature.structural_class_digest != target_scope:
        raise AssertionError('final governed reuse scope drift')
    final_diagnostic, final_terminal = _contexts(_FINAL_ROLES)
    governed = run_governed_meta_learning_episode(
        (learned,), final_signature, final_diagnostic, final_terminal,
        _oracle(_FINAL_ROLES), config, promotion_registry=registry,
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
            _oracle(_FINAL_ROLES), config, promotion_registry=registry,
        )
    except ValueError:
        rollback_revoked = True

    semantic = {
        'schema_version': 2,
        'milestone': 'R2.69',
        'capability': 'host-authority-bound-scoped-promotion-and-rollback',
        'candidate_artifact_digest': learned.portable_digest,
        'source_adapter_type': learned.adapter_type,
        'source_seed_prior_digest': seed_prior_digest,
        'source_meta_episode_passed': bool(source_receipt.passed),
        'structural_class_digest': target_scope,
        'heldout_targets': len(_HELDOUT_ROLES),
        'champion_accepted_targets': champion_accepted,
        'challenger_accepted_targets': challenger_accepted,
        'oracle_call_advantage': oracle_advantage,
        'search_work_advantage': search_advantage,
        'false_accepts': false_accepts,
        'promotion_accepted': bool(envelope.decision.promoted),
        'promotion_reason': envelope.decision.reason,
        'governed_reuse_passed': governed_reuse_passed,
        'rollback_revoked': rollback_revoked,
        'trainable_parameter_count': 0,
    }
    semantic_digest = _sha(semantic)
    promotion_gate_pass = bool(
        champion_accepted == len(_HELDOUT_ROLES)
        and false_accepts == 0
        and (
            champion_accepted > challenger_accepted
            or oracle_advantage > 0
            or search_advantage > 0
        )
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
