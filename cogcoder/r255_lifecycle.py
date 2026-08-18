from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r253_external_cognition import CognitiveSnapshot, DeficitSignal, ExternalWorkingState
from .r254_behavioral_retrieval import RetrievedCompiledProcedure, RetrievedProcedureAcquirer, RetrievedProcedureExecutor
from .r254_cognitive_retrieval import CognitiveAttachment
from .r255_reliability import SourceReliabilityLedger, _nonempty, _source_origin, _unit

@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    behavior_fingerprint: str
    previous_state: str
    new_state: str
    reason: str


class ProcedureLifecycleLedger:
    trainable_parameter_count = 0
    _allowed = {
        'unseen': {'candidate'},
        'candidate': {'probation', 'quarantined'},
        'probation': {'promoted', 'quarantined'},
        'promoted': {'rolled_back', 'quarantined'},
        'quarantined': set(),
        'rolled_back': set(),
    }

    def __init__(self) -> None:
        self._states: dict[str, str] = {}
        self._events: list[LifecycleEvent] = []

    def state(self, behavior_fingerprint: str) -> str:
        return self._states.get(str(behavior_fingerprint), 'unseen')

    def transition(self, behavior_fingerprint: str, new_state: str, *, reason: str) -> LifecycleEvent:
        behavior_fingerprint = _nonempty(behavior_fingerprint, 'behavior_fingerprint')
        new_state = _nonempty(new_state, 'new_state')
        reason = _nonempty(reason, 'reason')
        previous = self.state(behavior_fingerprint)
        if new_state not in self._allowed.get(previous, set()):
            raise ValueError(f'illegal lifecycle transition: {previous}->{new_state}')
        event = LifecycleEvent(behavior_fingerprint, previous, new_state, reason)
        self._states[behavior_fingerprint] = new_state
        self._events.append(event)
        return event

    def events(self) -> tuple[LifecycleEvent, ...]:
        return tuple(self._events)

    def snapshot(self) -> dict[str, object]:
        return {
            'states': {key: self._states[key] for key in sorted(self._states)},
            'events': [
                {
                    'behavior_fingerprint': event.behavior_fingerprint,
                    'previous_state': event.previous_state,
                    'new_state': event.new_state,
                    'reason': event.reason,
                }
                for event in self._events
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> 'ProcedureLifecycleLedger':
        ledger = cls()
        states = snapshot.get('states', {})
        events = snapshot.get('events', ())
        if not isinstance(states, Mapping) or isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
            raise TypeError('invalid lifecycle snapshot')
        for key, state in states.items():
            state = str(state)
            if state not in cls._allowed:
                raise ValueError(f'unknown lifecycle state: {state}')
            ledger._states[str(key)] = state
        for raw in events:
            if not isinstance(raw, Mapping):
                raise TypeError('lifecycle events must be mappings')
            ledger._events.append(LifecycleEvent(
                str(raw['behavior_fingerprint']),
                str(raw['previous_state']),
                str(raw['new_state']),
                str(raw['reason']),
            ))
        return ledger


@dataclass(frozen=True, slots=True)
class AcquisitionChallenge:
    name: str
    initial_context: Mapping[str, object]
    initial_capabilities: frozenset[str]
    expected_context: Mapping[str, object]
    expected_capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _nonempty(self.name, 'challenge name')


@dataclass(frozen=True, slots=True)
class ChallengeResult:
    challenge_name: str
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class PromotedBehavior:
    behavior_fingerprint: str
    representative_artifact_id: str
    compiled: object
    support_source_uris: tuple[str, ...]
    challenge_results: tuple[ChallengeResult, ...]


@dataclass(frozen=True, slots=True)
class QuarantinedBehavior:
    behavior_fingerprint: str
    artifact_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ProcedureEvaluationReceipt:
    promoted: tuple[PromotedBehavior, ...]
    quarantined: tuple[QuarantinedBehavior, ...]
    acquisition_rejections: tuple[object, ...]
    live_state_mutations: int


@dataclass(frozen=True, slots=True)
class LiveProcedureReceipt:
    success: bool
    rolled_back: bool
    behavior_fingerprint: str
    procedure_id: str
    reason: str
    executed_operator_ids: tuple[str, ...]


def _provenance_support_key(row: RetrievedCompiledProcedure) -> str:
    uri = row.attachment.source_uri
    if uri.startswith('nolane://distilled/'):
        try:
            payload = json.loads(row.attachment.text)
        except json.JSONDecodeError:
            payload = {}
        trajectory_id = str(payload.get('distilled_from_trajectory', '')).strip() if isinstance(payload, Mapping) else ''
        if trajectory_id:
            return f'trajectory:{trajectory_id}'
    return _source_origin(uri)


def _behavior_fingerprint(row: RetrievedCompiledProcedure) -> str:
    card = row.compiled.card
    payload = {
        'deficit_tags': sorted(card.deficit_tags),
        'context_tags': sorted(card.context_tags),
        'steps': list(card.steps),
        'preconditions': sorted(card.preconditions),
        'expected_outputs': sorted(card.expected_outputs),
        'verifier_operator_id': card.verifier_operator_id,
        'max_cost': float(card.max_cost),
        'max_risk': float(card.max_risk),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class HardenedProcedureAcquisitionEngine:
    """Quarantine-by-default lifecycle for behavioral knowledge acquired from retrieval."""

    trainable_parameter_count = 0

    def __init__(
        self,
        acquirer: RetrievedProcedureAcquirer,
        executor: RetrievedProcedureExecutor,
        reliability: SourceReliabilityLedger,
        lifecycle: ProcedureLifecycleLedger,
        *,
        min_independent_support: int = 2,
        min_effective_source_trust: float = 0.35,
        allowed_probation_side_effect_classes: frozenset[str] = frozenset({'state_only', 'pure'}),
    ) -> None:
        if int(min_independent_support) < 1:
            raise ValueError('min_independent_support must be positive')
        self.acquirer = acquirer
        self.executor = executor
        self.reliability = reliability
        self.lifecycle = lifecycle
        self.min_independent_support = int(min_independent_support)
        self.min_effective_source_trust = _unit(min_effective_source_trust, 'min_effective_source_trust')
        self.allowed_probation_side_effect_classes = frozenset(map(str, allowed_probation_side_effect_classes))
        if not self.allowed_probation_side_effect_classes:
            raise ValueError('allowed_probation_side_effect_classes must be non-empty')
        self._promoted: dict[str, RetrievedCompiledProcedure] = {}
        self._support_uris: dict[str, tuple[str, ...]] = {}

    @staticmethod
    def _restore_state(target: ExternalWorkingState, source: ExternalWorkingState) -> None:
        target.context.clear(); target.context.update(copy.deepcopy(source.context))
        target.capabilities.clear(); target.capabilities.update(source.capabilities)
        target.evidence[:] = list(source.evidence)
        target.hypotheses[:] = list(source.hypotheses)
        target.subgoals[:] = list(source.subgoals)
        target.representation_id = source.representation_id
        target.notes[:] = list(source.notes)

    def _challenge(
        self,
        candidate: RetrievedCompiledProcedure,
        challenge: AcquisitionChallenge,
        snapshot: CognitiveSnapshot,
        signal: DeficitSignal,
    ) -> ChallengeResult:
        state = ExternalWorkingState(
            context=copy.deepcopy(dict(challenge.initial_context)),
            capabilities=set(challenge.initial_capabilities),
        )
        receipt = self.executor.execute(candidate, state, snapshot, signal)
        if not receipt.success or not receipt.verified:
            return ChallengeResult(challenge.name, False, f'execution:{receipt.reason}')
        for key, expected in challenge.expected_context.items():
            if state.context.get(key) != expected:
                return ChallengeResult(challenge.name, False, f'context:{key}')
        missing = set(challenge.expected_capabilities).difference(state.capabilities)
        if missing:
            return ChallengeResult(challenge.name, False, f'capabilities:{sorted(missing)}')
        return ChallengeResult(challenge.name, True, 'passed')

    def evaluate(
        self,
        attachments: Sequence[CognitiveAttachment],
        challenges: Sequence[AcquisitionChallenge],
        snapshot: CognitiveSnapshot,
        signal: DeficitSignal,
    ) -> ProcedureEvaluationReceipt:
        acquisition = self.acquirer.acquire(attachments)
        groups: dict[str, list[RetrievedCompiledProcedure]] = defaultdict(list)
        for row in acquisition.accepted:
            effective = self.reliability.effective_trust(row.attachment.source_uri, row.attachment.trust_score)
            if effective >= self.min_effective_source_trust:
                groups[_behavior_fingerprint(row)].append(row)

        promoted: list[PromotedBehavior] = []
        quarantined: list[QuarantinedBehavior] = []
        for fingerprint in sorted(groups):
            candidates = groups[fingerprint]
            candidates.sort(key=lambda row: (
                -self.reliability.effective_trust(row.attachment.source_uri, row.attachment.trust_score),
                -row.attachment.activation,
                row.artifact_id,
            ))
            source_origins = {}
            for row in candidates:
                source_origins.setdefault(_provenance_support_key(row), row.attachment.source_uri)
            support_uris = tuple(source_origins[key] for key in sorted(source_origins))

            current = self.lifecycle.state(fingerprint)
            if current == 'unseen':
                self.lifecycle.transition(fingerprint, 'candidate', reason='retrieved_and_compiled')
                current = 'candidate'
            if current in {'quarantined', 'rolled_back'}:
                quarantined.append(QuarantinedBehavior(fingerprint, tuple(row.artifact_id for row in candidates), f'lifecycle_terminal:{current}'))
                continue
            if len(support_uris) < self.min_independent_support:
                if current == 'candidate':
                    self.lifecycle.transition(fingerprint, 'quarantined', reason='insufficient_independent_support')
                quarantined.append(QuarantinedBehavior(fingerprint, tuple(row.artifact_id for row in candidates), 'insufficient_independent_support'))
                continue
            if current == 'candidate':
                self.lifecycle.transition(fingerprint, 'probation', reason=f'independent_support:{len(support_uris)}')
                current = 'probation'

            representative = candidates[0]
            unsupported_side_effects = sorted({
                operator.side_effect_class for operator in representative.compiled.operators
                if operator.side_effect_class not in self.allowed_probation_side_effect_classes
            })
            if unsupported_side_effects:
                reason = f'unsupported_side_effect_class:{unsupported_side_effects[0]}'
                if current == 'probation':
                    self.lifecycle.transition(fingerprint, 'quarantined', reason=reason)
                quarantined.append(QuarantinedBehavior(
                    fingerprint, tuple(row.artifact_id for row in candidates), reason,
                ))
                continue
            results = tuple(self._challenge(representative, challenge, snapshot, signal) for challenge in challenges)
            failure = next((result for result in results if not result.passed), None)
            if failure is not None:
                if current == 'probation':
                    self.lifecycle.transition(fingerprint, 'quarantined', reason=f'challenge_failed:{failure.challenge_name}:{failure.reason}')
                quarantined.append(QuarantinedBehavior(
                    fingerprint,
                    tuple(row.artifact_id for row in candidates),
                    f'challenge_failed:{failure.challenge_name}:{failure.reason}',
                ))
                for row in candidates:
                    self.reliability.record(row.attachment.source_uri, success=False)
                continue

            if current == 'probation':
                self.lifecycle.transition(fingerprint, 'promoted', reason=f'challenges_passed:{len(results)}')
            self._promoted[fingerprint] = representative
            self._support_uris[fingerprint] = support_uris
            for row in candidates:
                self.reliability.record(row.attachment.source_uri, success=True)
            promoted.append(PromotedBehavior(
                fingerprint,
                representative.artifact_id,
                representative.compiled,
                support_uris,
                results,
            ))

        return ProcedureEvaluationReceipt(tuple(promoted), tuple(quarantined), tuple(acquisition.rejected), 0)

    def execute_promoted(
        self,
        behavior_fingerprint: str,
        state: ExternalWorkingState,
        snapshot: CognitiveSnapshot,
        signal: DeficitSignal,
    ) -> LiveProcedureReceipt:
        fingerprint = str(behavior_fingerprint)
        if self.lifecycle.state(fingerprint) != 'promoted' or fingerprint not in self._promoted:
            return LiveProcedureReceipt(False, False, fingerprint, '', 'behavior_not_promoted', ())
        candidate = self._promoted[fingerprint]
        before = copy.deepcopy(state)
        receipt = self.executor.execute(candidate, state, snapshot, signal)
        if not receipt.success or not receipt.verified:
            self._restore_state(state, before)
            self.lifecycle.transition(fingerprint, 'rolled_back', reason=f'live_failure:{receipt.reason}')
            for uri in self._support_uris.get(fingerprint, ()):
                self.reliability.record(uri, success=False)
            return LiveProcedureReceipt(
                False,
                True,
                fingerprint,
                receipt.procedure_id,
                receipt.reason,
                receipt.executed_operator_ids,
            )
        for uri in self._support_uris.get(fingerprint, ()):
            self.reliability.record(uri, success=True)
        return LiveProcedureReceipt(
            True,
            False,
            fingerprint,
            receipt.procedure_id,
            receipt.reason,
            receipt.executed_operator_ids,
        )

