from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

_ALLOWED_KINDS = frozenset({'portable_prior', 'procedure'})
_HEX64 = re.compile(r'^[0-9a-f]{64}$')
_FORBIDDEN_SCOPE_NAMES = frozenset({'global', 'all', 'universal', '*'})


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f'{name} must be non-empty')
    return text


def _scope(value: object) -> str:
    text = _nonempty(value, 'structural_class_digest').lower()
    if text in _FORBIDDEN_SCOPE_NAMES or _HEX64.fullmatch(text) is None:
        raise ValueError('structural_class_digest must be one exact 64-hex structural scope digest')
    return text


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class PromotionCandidate:
    candidate_kind: str
    artifact_digest: str
    structural_class_digest: str
    freeze_receipt_digest: str
    rollback_identity: str
    trainable_parameter_count: int = 0

    def __post_init__(self) -> None:
        kind = _nonempty(self.candidate_kind, 'candidate_kind')
        if kind not in _ALLOWED_KINDS:
            raise ValueError('candidate_kind must be portable_prior or procedure')
        if self.trainable_parameter_count != 0:
            raise ValueError('trainable_parameter_count must remain zero')
        object.__setattr__(self, 'candidate_kind', kind)
        object.__setattr__(self, 'artifact_digest', _nonempty(self.artifact_digest, 'artifact_digest'))
        object.__setattr__(self, 'structural_class_digest', _scope(self.structural_class_digest))
        object.__setattr__(self, 'freeze_receipt_digest', _nonempty(self.freeze_receipt_digest, 'freeze_receipt_digest'))
        object.__setattr__(self, 'rollback_identity', _nonempty(self.rollback_identity, 'rollback_identity'))


@dataclass(frozen=True, slots=True)
class ChampionChallengerEvidence:
    candidate_artifact_digest: str
    preregistered_scope_digest: str
    champion_receipt_digest: str
    challenger_receipt_digest: str
    terminal_verifier_digest: str
    candidate_issuer: str
    verifier_issuer: str
    heldout_targets: int
    champion_accepted_targets: int
    challenger_accepted_targets: int
    oracle_call_advantage: int
    search_work_advantage: int
    protected_regression_failures: int
    false_accepts: int
    budget_accounting_exact: bool
    terminal_verification_passed: bool
    target_answer_channel_detected: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, 'candidate_artifact_digest', _nonempty(self.candidate_artifact_digest, 'candidate_artifact_digest'))
        object.__setattr__(self, 'preregistered_scope_digest', _scope(self.preregistered_scope_digest))
        object.__setattr__(self, 'champion_receipt_digest', _nonempty(self.champion_receipt_digest, 'champion_receipt_digest'))
        object.__setattr__(self, 'challenger_receipt_digest', _nonempty(self.challenger_receipt_digest, 'challenger_receipt_digest'))
        object.__setattr__(self, 'terminal_verifier_digest', _nonempty(self.terminal_verifier_digest, 'terminal_verifier_digest'))
        object.__setattr__(self, 'candidate_issuer', _nonempty(self.candidate_issuer, 'candidate_issuer'))
        object.__setattr__(self, 'verifier_issuer', _nonempty(self.verifier_issuer, 'verifier_issuer'))
        if self.heldout_targets < 1:
            raise ValueError('heldout_targets must be positive')
        if not (0 <= self.champion_accepted_targets <= self.heldout_targets):
            raise ValueError('champion_accepted_targets outside heldout target count')
        if not (0 <= self.challenger_accepted_targets <= self.heldout_targets):
            raise ValueError('challenger_accepted_targets outside heldout target count')
        if self.protected_regression_failures < 0 or self.false_accepts < 0:
            raise ValueError('failure counters must be non-negative')
        for name in ('budget_accounting_exact', 'terminal_verification_passed', 'target_answer_channel_detected'):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f'{name} must be bool')

    @property
    def evidence_digest(self) -> str:
        payload = {
            'schema_version': 1,
            'candidate_artifact_digest': self.candidate_artifact_digest,
            'preregistered_scope_digest': self.preregistered_scope_digest,
            'champion_receipt_digest': self.champion_receipt_digest,
            'challenger_receipt_digest': self.challenger_receipt_digest,
            'terminal_verifier_digest': self.terminal_verifier_digest,
            'candidate_issuer': self.candidate_issuer,
            'verifier_issuer': self.verifier_issuer,
            'heldout_targets': self.heldout_targets,
            'champion_accepted_targets': self.champion_accepted_targets,
            'challenger_accepted_targets': self.challenger_accepted_targets,
            'oracle_call_advantage': self.oracle_call_advantage,
            'search_work_advantage': self.search_work_advantage,
            'protected_regression_failures': self.protected_regression_failures,
            'false_accepts': self.false_accepts,
            'budget_accounting_exact': self.budget_accounting_exact,
            'terminal_verification_passed': self.terminal_verification_passed,
            'target_answer_channel_detected': self.target_answer_channel_detected,
        }
        return 'r269.promotion-evidence.' + _sha(payload)


def _decision_payload(*, promoted: bool, candidate_kind: str, candidate_artifact_digest: str,
                      structural_class_digest: str, rollback_identity: str,
                      evidence_digest: str, reason: str, trainable_parameter_count: int) -> dict[str, object]:
    return {
        'schema_version': 1,
        'promoted': promoted,
        'candidate_kind': candidate_kind,
        'candidate_artifact_digest': candidate_artifact_digest,
        'structural_class_digest': structural_class_digest,
        'rollback_identity': rollback_identity,
        'evidence_digest': evidence_digest,
        'reason': reason,
        'trainable_parameter_count': trainable_parameter_count,
    }


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promoted: bool
    candidate_kind: str
    candidate_artifact_digest: str
    structural_class_digest: str
    rollback_identity: str
    evidence_digest: str
    reason: str
    decision_digest: str
    trainable_parameter_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.promoted, bool):
            raise TypeError('promoted must be bool')
        if self.trainable_parameter_count != 0:
            raise ValueError('trainable_parameter_count must remain zero')
        kind = _nonempty(self.candidate_kind, 'candidate_kind')
        if kind not in _ALLOWED_KINDS:
            raise ValueError('unsupported candidate_kind')
        artifact = _nonempty(self.candidate_artifact_digest, 'candidate_artifact_digest')
        scope = _scope(self.structural_class_digest)
        rollback = _nonempty(self.rollback_identity, 'rollback_identity')
        evidence = _nonempty(self.evidence_digest, 'evidence_digest')
        reason = _nonempty(self.reason, 'reason')
        payload = _decision_payload(
            promoted=self.promoted,
            candidate_kind=kind,
            candidate_artifact_digest=artifact,
            structural_class_digest=scope,
            rollback_identity=rollback,
            evidence_digest=evidence,
            reason=reason,
            trainable_parameter_count=0,
        )
        expected = 'r269.promotion-decision.' + _sha(payload)
        if self.decision_digest != expected:
            raise ValueError('decision_digest must bind exact scoped promotion decision content')
        object.__setattr__(self, 'candidate_kind', kind)
        object.__setattr__(self, 'candidate_artifact_digest', artifact)
        object.__setattr__(self, 'structural_class_digest', scope)
        object.__setattr__(self, 'rollback_identity', rollback)
        object.__setattr__(self, 'evidence_digest', evidence)
        object.__setattr__(self, 'reason', reason)


class ScopedPromotionController:
    def adjudicate(self, candidate: PromotionCandidate, evidence: ChampionChallengerEvidence) -> PromotionDecision:
        if not isinstance(candidate, PromotionCandidate):
            raise TypeError('candidate must be PromotionCandidate')
        if not isinstance(evidence, ChampionChallengerEvidence):
            raise TypeError('evidence must be ChampionChallengerEvidence')

        if evidence.candidate_artifact_digest != candidate.artifact_digest:
            promoted, reason = False, 'candidate_artifact_mismatch'
        elif evidence.preregistered_scope_digest != candidate.structural_class_digest:
            promoted, reason = False, 'scope_mismatch'
        elif evidence.candidate_issuer == evidence.verifier_issuer:
            promoted, reason = False, 'independent_verifier_required'
        elif evidence.champion_accepted_targets < 1:
            promoted, reason = False, 'champion_not_accepted'
        elif (
            evidence.champion_accepted_targets <= evidence.challenger_accepted_targets
            and evidence.oracle_call_advantage <= 0
            and evidence.search_work_advantage <= 0
        ):
            promoted, reason = False, 'challenger_advantage_not_proven'
        elif evidence.protected_regression_failures != 0:
            promoted, reason = False, 'protected_regression_loss'
        elif not evidence.budget_accounting_exact:
            promoted, reason = False, 'budget_accounting_inexact'
        elif not evidence.terminal_verification_passed:
            promoted, reason = False, 'terminal_verification_missing'
        elif evidence.target_answer_channel_detected:
            promoted, reason = False, 'target_answer_channel_detected'
        elif evidence.false_accepts != 0:
            promoted, reason = False, 'false_accepts_present'
        else:
            promoted, reason = True, 'scoped_promotion_accepted'

        payload = _decision_payload(
            promoted=promoted,
            candidate_kind=candidate.candidate_kind,
            candidate_artifact_digest=candidate.artifact_digest,
            structural_class_digest=candidate.structural_class_digest,
            rollback_identity=candidate.rollback_identity,
            evidence_digest=evidence.evidence_digest,
            reason=reason,
            trainable_parameter_count=0,
        )
        return PromotionDecision(
            promoted=promoted,
            candidate_kind=candidate.candidate_kind,
            candidate_artifact_digest=candidate.artifact_digest,
            structural_class_digest=candidate.structural_class_digest,
            rollback_identity=candidate.rollback_identity,
            evidence_digest=evidence.evidence_digest,
            reason=reason,
            decision_digest='r269.promotion-decision.' + _sha(payload),
            trainable_parameter_count=0,
        )


__all__ = [
    'PromotionCandidate',
    'ChampionChallengerEvidence',
    'PromotionDecision',
    'ScopedPromotionController',
]
