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
    freeze_receipt_digest: str
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
        object.__setattr__(self, 'freeze_receipt_digest', _nonempty(self.freeze_receipt_digest, 'freeze_receipt_digest'))
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
            'freeze_receipt_digest': self.freeze_receipt_digest,
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
                      freeze_receipt_digest: str, structural_class_digest: str, rollback_identity: str,
                      evidence_digest: str, reason: str, trainable_parameter_count: int) -> dict[str, object]:
    return {
        'schema_version': 1,
        'promoted': promoted,
        'candidate_kind': candidate_kind,
        'candidate_artifact_digest': candidate_artifact_digest,
        'freeze_receipt_digest': freeze_receipt_digest,
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
    freeze_receipt_digest: str
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
        freeze = _nonempty(self.freeze_receipt_digest, 'freeze_receipt_digest')
        scope = _scope(self.structural_class_digest)
        rollback = _nonempty(self.rollback_identity, 'rollback_identity')
        evidence = _nonempty(self.evidence_digest, 'evidence_digest')
        reason = _nonempty(self.reason, 'reason')
        payload = _decision_payload(
            promoted=self.promoted,
            candidate_kind=kind,
            candidate_artifact_digest=artifact,
            freeze_receipt_digest=freeze,
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
        object.__setattr__(self, 'freeze_receipt_digest', freeze)
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
        elif evidence.freeze_receipt_digest != candidate.freeze_receipt_digest:
            promoted, reason = False, 'freeze_receipt_mismatch'
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
            freeze_receipt_digest=candidate.freeze_receipt_digest,
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
            freeze_receipt_digest=candidate.freeze_receipt_digest,
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

_ALLOWED_REGISTRY_ACTIONS = frozenset({'activate', 'rollback'})


def _promotion_event_payload(*, action: str, structural_class_digest: str, decision_digest: str,
                             rollback_identity: str, previous_event_digest: str | None) -> dict[str, object]:
    return {
        'schema_version': 1,
        'action': action,
        'structural_class_digest': structural_class_digest,
        'decision_digest': decision_digest,
        'rollback_identity': rollback_identity,
        'previous_event_digest': previous_event_digest,
    }


@dataclass(frozen=True, slots=True)
class PromotionRegistryEvent:
    action: str
    structural_class_digest: str
    decision_digest: str
    rollback_identity: str
    previous_event_digest: str | None
    event_digest: str

    def __post_init__(self) -> None:
        action = _nonempty(self.action, 'action')
        if action not in _ALLOWED_REGISTRY_ACTIONS:
            raise ValueError('unsupported registry action')
        scope = _scope(self.structural_class_digest)
        decision = _nonempty(self.decision_digest, 'decision_digest')
        rollback = _nonempty(self.rollback_identity, 'rollback_identity')
        previous = None if self.previous_event_digest is None else _nonempty(
            self.previous_event_digest, 'previous_event_digest'
        )
        payload = _promotion_event_payload(
            action=action,
            structural_class_digest=scope,
            decision_digest=decision,
            rollback_identity=rollback,
            previous_event_digest=previous,
        )
        expected = 'r269.promotion-event.' + _sha(payload)
        if self.event_digest != expected:
            raise ValueError('event_digest must bind exact promotion registry event content')
        object.__setattr__(self, 'action', action)
        object.__setattr__(self, 'structural_class_digest', scope)
        object.__setattr__(self, 'decision_digest', decision)
        object.__setattr__(self, 'rollback_identity', rollback)
        object.__setattr__(self, 'previous_event_digest', previous)


class ScopedPromotionRegistry:
    def __init__(self) -> None:
        self._active: dict[str, PromotionDecision] = {}
        self._history: list[PromotionRegistryEvent] = []

    @property
    def history(self) -> tuple[PromotionRegistryEvent, ...]:
        return tuple(self._history)

    @property
    def event_head(self) -> str | None:
        return self._history[-1].event_digest if self._history else None

    def active_for(self, structural_class_digest: str) -> PromotionDecision | None:
        return self._active.get(_scope(structural_class_digest))

    def _event(self, action: str, decision: PromotionDecision) -> PromotionRegistryEvent:
        payload = _promotion_event_payload(
            action=action,
            structural_class_digest=decision.structural_class_digest,
            decision_digest=decision.decision_digest,
            rollback_identity=decision.rollback_identity,
            previous_event_digest=self.event_head,
        )
        return PromotionRegistryEvent(
            action=action,
            structural_class_digest=decision.structural_class_digest,
            decision_digest=decision.decision_digest,
            rollback_identity=decision.rollback_identity,
            previous_event_digest=self.event_head,
            event_digest='r269.promotion-event.' + _sha(payload),
        )

    def activate(self, decision: PromotionDecision) -> PromotionRegistryEvent:
        if not isinstance(decision, PromotionDecision):
            raise TypeError('decision must be PromotionDecision')
        if not decision.promoted:
            raise ValueError('registry activation requires a promoted decision')
        scope = decision.structural_class_digest
        current = self._active.get(scope)
        if current is not None:
            if current.decision_digest == decision.decision_digest:
                for event in reversed(self._history):
                    if event.action == 'activate' and event.decision_digest == decision.decision_digest:
                        return event
                raise RuntimeError('active decision has no activation event')
            raise ValueError('structural scope already has an active promotion; rollback is required first')
        event = self._event('activate', decision)
        self._history.append(event)
        self._active[scope] = decision
        return event

    def rollback(
        self,
        structural_class_digest: str,
        *,
        rollback_identity: str,
        expected_decision_digest: str,
    ) -> PromotionRegistryEvent:
        scope = _scope(structural_class_digest)
        current = self._active.get(scope)
        if current is None:
            raise ValueError('structural scope has no active promotion')
        rollback = _nonempty(rollback_identity, 'rollback_identity')
        expected = _nonempty(expected_decision_digest, 'expected_decision_digest')
        if rollback != current.rollback_identity:
            raise ValueError('rollback_identity does not match active promotion')
        if expected != current.decision_digest:
            raise ValueError('expected_decision_digest does not match active promotion')
        event = self._event('rollback', current)
        self._history.append(event)
        del self._active[scope]
        return event

    def audit(self) -> bool:
        previous: str | None = None
        reconstructed: dict[str, str] = {}
        for event in self._history:
            payload = _promotion_event_payload(
                action=event.action,
                structural_class_digest=event.structural_class_digest,
                decision_digest=event.decision_digest,
                rollback_identity=event.rollback_identity,
                previous_event_digest=previous,
            )
            expected = 'r269.promotion-event.' + _sha(payload)
            if event.previous_event_digest != previous or event.event_digest != expected:
                return False
            if event.action == 'activate':
                if event.structural_class_digest in reconstructed:
                    return False
                reconstructed[event.structural_class_digest] = event.decision_digest
            else:
                if reconstructed.get(event.structural_class_digest) != event.decision_digest:
                    return False
                del reconstructed[event.structural_class_digest]
            previous = event.event_digest
        active = {scope: decision.decision_digest for scope, decision in self._active.items()}
        return reconstructed == active


__all__.extend(['PromotionRegistryEvent', 'ScopedPromotionRegistry'])
