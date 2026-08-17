from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence


Executor = Callable[['ExternalWorkingState', 'CognitiveSnapshot', 'DeficitSignal'], Mapping[str, object]]


def _unit(value: float, field_name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f'{field_name} must be in [0,1]')
    return value


def _nonempty(value: str, field_name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f'{field_name} must be non-empty')
    return value


@dataclass(frozen=True, slots=True)
class CognitiveSnapshot:
    objective: str
    step_index: int
    self_confidence: float
    progress_score: float
    previous_progress_score: float
    unresolved_requirements: tuple[str, ...] = ()
    evidence_coverage: float = 1.0
    verifier_failures: int = 0
    recent_action_fingerprints: tuple[str, ...] = ()
    representation_id: str = 'default'
    representation_failures: int = 0
    available_capabilities: frozenset[str] = frozenset()
    missing_capabilities: frozenset[str] = frozenset()
    evidence_conflicts: int = 0
    stale_evidence: int = 0
    blocked_subgoals: int = 0
    working_memory_pressure: float = 0.0
    counterexample_repeat_count: int = 0
    resource_pressure: float = 0.0
    candidate_verified: bool = False
    terminal_candidate: bool = False
    host_observations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.objective, 'objective')
        if int(self.step_index) < 0:
            raise ValueError('step_index must be non-negative')
        _unit(self.self_confidence, 'self_confidence')
        _unit(self.progress_score, 'progress_score')
        _unit(self.previous_progress_score, 'previous_progress_score')
        _unit(self.evidence_coverage, 'evidence_coverage')
        _unit(self.working_memory_pressure, 'working_memory_pressure')
        _unit(self.resource_pressure, 'resource_pressure')
        for name in ('verifier_failures', 'representation_failures', 'evidence_conflicts', 'stale_evidence', 'blocked_subgoals', 'counterexample_repeat_count'):
            if int(getattr(self, name)) < 0:
                raise ValueError(f'{name} must be non-negative')


@dataclass(frozen=True, slots=True)
class DeficitSignal:
    kind: str
    severity: float
    confidence: float
    source: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.kind, 'kind')
        _unit(self.severity, 'severity')
        _unit(self.confidence, 'confidence')
        if self.source not in {'objective', 'self_report', 'mixed'}:
            raise ValueError('source must be objective, self_report, or mixed')


class CognitiveDeficitDetector:
    """Deterministic, externally observable metacognitive deficit detector.

    It deliberately does not trust model self-confidence as an authority. Objective signals such
    as verifier failures, repeated actions, conflicts, and blocked dependencies can generate a
    high-severity deficit even when self-confidence is 1.0.
    """

    trainable_parameter_count = 0

    def detect(self, snapshot: CognitiveSnapshot) -> tuple[DeficitSignal, ...]:
        out: list[DeficitSignal] = []

        def emit(kind: str, severity: float, confidence: float, *evidence: str, source: str = 'objective') -> None:
            out.append(DeficitSignal(kind, min(1.0, max(0.0, severity)), min(1.0, max(0.0, confidence)), source, tuple(evidence)))

        unresolved = tuple(x for x in snapshot.unresolved_requirements if str(x).strip())
        if unresolved and snapshot.evidence_coverage < 0.8:
            sev = max(0.55, 1.0 - snapshot.evidence_coverage)
            emit('knowledge_gap', sev, 0.95, f'unresolved={len(unresolved)}', f'evidence_coverage={snapshot.evidence_coverage:.3f}')
            emit('information_acquisition_gap', min(1.0, sev + 0.05), 0.9, 'missing evidence for unresolved requirements')

        if snapshot.missing_capabilities:
            missing = sorted(snapshot.missing_capabilities)
            tool_missing = [value for value in missing if value.startswith('tool:')]
            skill_missing = [value for value in missing if value.startswith('skill:')]
            math_missing = [value for value in missing if value.startswith('math:')]
            code_missing = [value for value in missing if value.startswith('code:')]
            other_missing = [value for value in missing if value not in set(tool_missing + skill_missing + math_missing + code_missing)]
            if tool_missing:
                emit('tool_gap', min(1.0, 0.65 + 0.07 * len(tool_missing)), 0.98, *tool_missing)
            if skill_missing:
                emit('skill_gap', min(1.0, 0.65 + 0.07 * len(skill_missing)), 0.96, *skill_missing)
            if math_missing:
                emit('mathematical_support_gap', min(1.0, 0.65 + 0.07 * len(math_missing)), 0.96, *math_missing)
            if code_missing:
                emit('code_analysis_gap', min(1.0, 0.65 + 0.07 * len(code_missing)), 0.96, *code_missing)
            if other_missing:
                emit('capability_gap', min(1.0, 0.62 + 0.06 * len(other_missing)), 0.9, *other_missing)

        if snapshot.evidence_conflicts:
            emit('contradiction', min(1.0, 0.65 + 0.1 * snapshot.evidence_conflicts), 0.98, f'conflicts={snapshot.evidence_conflicts}')

        if snapshot.stale_evidence:
            emit('temporal_conflict', min(1.0, 0.6 + 0.1 * snapshot.stale_evidence), 0.94, f'stale_evidence={snapshot.stale_evidence}')

        if snapshot.representation_failures >= 2:
            emit('representation_mismatch', min(1.0, 0.72 + 0.08 * snapshot.representation_failures), 0.9, f'representation={snapshot.representation_id}', f'failures={snapshot.representation_failures}')

        if snapshot.blocked_subgoals:
            emit('planning_gap', min(1.0, 0.6 + 0.08 * snapshot.blocked_subgoals), 0.9, f'blocked_subgoals={snapshot.blocked_subgoals}')

        if snapshot.working_memory_pressure >= 0.8:
            emit('working_memory_pressure', snapshot.working_memory_pressure, 0.95, f'pressure={snapshot.working_memory_pressure:.3f}')

        if snapshot.counterexample_repeat_count:
            emit('counterexample_gap', min(1.0, 0.65 + 0.1 * snapshot.counterexample_repeat_count), 0.98, f'repeated_falsifier={snapshot.counterexample_repeat_count}')

        if snapshot.resource_pressure >= 0.8:
            emit('resource_pressure', snapshot.resource_pressure, 0.95, f'pressure={snapshot.resource_pressure:.3f}')

        recent = snapshot.recent_action_fingerprints
        repeated = len(recent) >= 3 and len(set(recent[-3:])) == 1
        no_progress = snapshot.progress_score <= snapshot.previous_progress_score + 1e-12
        if repeated and no_progress:
            emit('search_stagnation', 0.9 if len(recent) < 5 else 1.0, 0.99, f'repeated_action={recent[-1]}', f'progress_delta={snapshot.progress_score-snapshot.previous_progress_score:.6f}')

        if snapshot.verifier_failures > 0:
            emit('verification_gap', min(1.0, 0.75 + 0.08 * snapshot.verifier_failures), 0.99, f'verifier_failures={snapshot.verifier_failures}')
        elif snapshot.terminal_candidate and not snapshot.candidate_verified:
            emit('verification_gap', 0.8, 0.96, 'terminal candidate lacks independent verification')

        if not snapshot.candidate_verified and not snapshot.terminal_candidate:
            emit('stopping_uncertainty', 0.55, 0.8, 'trajectory has no verified terminal candidate')

        if snapshot.self_confidence < 0.35 and not any(row.kind == 'knowledge_gap' for row in out):
            emit('uncertainty_gap', 0.65, 0.7, f'self_confidence={snapshot.self_confidence:.3f}', source='self_report')

        observation_map = {
            'causal_gap:': ('causal_gap', 0.72, 0.9),
            'goal_ambiguous:': ('goal_ambiguity', 0.7, 0.88),
            'constraint_violation:': ('constraint_violation', 0.9, 0.99),
            'routing_uncertain:': ('routing_uncertainty', 0.66, 0.85),
            'episode_missing:': ('episodic_gap', 0.62, 0.84),
            'novelty_gap:': ('novelty_gap', 0.58, 0.8),
            'credit_ambiguous:': ('credit_ambiguity', 0.6, 0.82),
        }
        for observation in snapshot.host_observations:
            text = str(observation).strip()
            for prefix, (kind, severity, confidence) in observation_map.items():
                if text.startswith(prefix):
                    emit(kind, severity, confidence, text[len(prefix):].strip() or text)
                    break

        # Stable deterministic order: severity first, then objective confidence, then kind.
        out.sort(key=lambda row: (-row.severity, -row.confidence, row.kind, row.evidence))
        return tuple(out)


@dataclass(frozen=True)
class CognitiveOperatorSpec:
    operator_id: str
    family: str
    tags: frozenset[str]
    requires: frozenset[str]
    provides: frozenset[str]
    cost: float
    risk: float
    side_effect_class: str
    version: str
    source_uri: str
    executor: Executor

    def __post_init__(self) -> None:
        _nonempty(self.operator_id, 'operator_id')
        _nonempty(self.family, 'family')
        _nonempty(self.side_effect_class, 'side_effect_class')
        _nonempty(self.version, 'version')
        _nonempty(self.source_uri, 'source_uri')
        if not callable(self.executor):
            raise TypeError('executor must be callable')
        if float(self.cost) < 0:
            raise ValueError('cost must be non-negative')
        _unit(self.risk, 'risk')


class CognitiveOperatorRegistry:
    trainable_parameter_count = 0

    def __init__(self, operators: Iterable[CognitiveOperatorSpec] = ()) -> None:
        self._operators: dict[str, CognitiveOperatorSpec] = {}
        for operator in operators:
            self.register(operator)

    def register(self, operator: CognitiveOperatorSpec) -> CognitiveOperatorSpec:
        previous = self._operators.get(operator.operator_id)
        if previous is not None:
            if previous != operator:
                raise ValueError(f'operator id collision: {operator.operator_id}')
            return previous
        self._operators[operator.operator_id] = operator
        return operator

    def has(self, operator_id: str) -> bool:
        return str(operator_id) in self._operators

    def get(self, operator_id: str) -> CognitiveOperatorSpec:
        try:
            return self._operators[str(operator_id)]
        except KeyError as exc:
            raise KeyError(str(operator_id)) from exc

    def operators(self) -> tuple[CognitiveOperatorSpec, ...]:
        return tuple(self._operators[key] for key in sorted(self._operators))


def make_procedure_digest(
    *,
    procedure_id: str,
    version: str,
    deficit_tags: frozenset[str],
    context_tags: frozenset[str],
    steps: tuple[str, ...],
    preconditions: frozenset[str],
    expected_outputs: frozenset[str],
    verifier_operator_id: str | None,
    max_cost: float,
    max_risk: float,
    trust_score: float,
    source_uri: str,
) -> str:
    payload = {
        'procedure_id': str(procedure_id),
        'version': str(version),
        'deficit_tags': sorted(map(str, deficit_tags)),
        'context_tags': sorted(map(str, context_tags)),
        'steps': list(map(str, steps)),
        'preconditions': sorted(map(str, preconditions)),
        'expected_outputs': sorted(map(str, expected_outputs)),
        'verifier_operator_id': None if verifier_operator_id is None else str(verifier_operator_id),
        'max_cost': float(max_cost),
        'max_risk': float(max_risk),
        'trust_score': float(trust_score),
        'source_uri': str(source_uri),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class ProcedureCard:
    procedure_id: str
    version: str
    deficit_tags: frozenset[str]
    context_tags: frozenset[str]
    steps: tuple[str, ...]
    preconditions: frozenset[str]
    expected_outputs: frozenset[str]
    verifier_operator_id: str | None
    max_cost: float
    max_risk: float
    trust_score: float
    source_uri: str
    content_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.procedure_id, 'procedure_id')
        _nonempty(self.version, 'version')
        _nonempty(self.source_uri, 'source_uri')
        if not self.deficit_tags:
            raise ValueError('procedure must target at least one deficit')
        if not self.steps:
            raise ValueError('procedure must contain at least one operator step')
        if len(set(self.steps)) != len(self.steps):
            # Repeating an operator can be valid in a richer loop DSL, but R2.53 cards are bounded straight-line programs.
            raise ValueError('R2.53 procedure steps must be unique')
        if float(self.max_cost) < 0:
            raise ValueError('max_cost must be non-negative')
        _unit(self.max_risk, 'max_risk')
        _unit(self.trust_score, 'trust_score')
        if len(self.content_sha256) != 64:
            raise ValueError('content_sha256 must be a SHA-256 hex digest')

    def expected_digest(self) -> str:
        return make_procedure_digest(
            procedure_id=self.procedure_id,
            version=self.version,
            deficit_tags=self.deficit_tags,
            context_tags=self.context_tags,
            steps=self.steps,
            preconditions=self.preconditions,
            expected_outputs=self.expected_outputs,
            verifier_operator_id=self.verifier_operator_id,
            max_cost=self.max_cost,
            max_risk=self.max_risk,
            trust_score=self.trust_score,
            source_uri=self.source_uri,
        )


class ProcedureLibrary:
    trainable_parameter_count = 0

    def __init__(self, cards: Iterable[ProcedureCard]) -> None:
        self._cards: dict[tuple[str, str], ProcedureCard] = {}
        for card in cards:
            key = (card.procedure_id, card.version)
            previous = self._cards.get(key)
            if previous is not None and previous != card:
                raise ValueError(f'procedure identity collision: {key}')
            self._cards[key] = card

    def search(self, deficit_kind: str, context_tags: Iterable[str], *, k: int = 5) -> tuple[ProcedureCard, ...]:
        if int(k) < 1:
            raise ValueError('k must be positive')
        deficit_kind = _nonempty(deficit_kind, 'deficit_kind')
        context = {str(tag) for tag in context_tags}
        scored: list[tuple[float, ProcedureCard]] = []
        for card in self._cards.values():
            if deficit_kind not in card.deficit_tags:
                continue
            overlap = len(context.intersection(card.context_tags))
            union = max(1, len(context.union(card.context_tags)))
            context_score = overlap / union
            exact_bonus = 0.15 if card.context_tags and card.context_tags <= context else 0.0
            score = 2.0 + context_score + exact_bonus + 0.25 * card.trust_score
            scored.append((score, card))
        scored.sort(key=lambda row: (-row[0], -row[1].trust_score, row[1].procedure_id, row[1].version))
        return tuple(card for _score, card in scored[: int(k)])


@dataclass(frozen=True)
class CompiledProcedure:
    card: ProcedureCard
    operators: tuple[CognitiveOperatorSpec, ...]
    total_cost: float
    total_risk: float
    provided_capabilities: frozenset[str]

    @property
    def procedure_id(self) -> str:
        return self.card.procedure_id

    @property
    def context_tags(self) -> frozenset[str]:
        return self.card.context_tags


class ProcedureCompiler:
    trainable_parameter_count = 0

    def __init__(self, registry: CognitiveOperatorRegistry, *, min_trust: float = 0.75, global_max_steps: int = 16) -> None:
        self.registry = registry
        self.min_trust = _unit(min_trust, 'min_trust')
        if int(global_max_steps) < 1:
            raise ValueError('global_max_steps must be positive')
        self.global_max_steps = int(global_max_steps)

    def compile(self, card: ProcedureCard) -> CompiledProcedure:
        if card.expected_digest() != card.content_sha256:
            raise ValueError('procedure provenance digest mismatch')
        if card.trust_score < self.min_trust:
            raise ValueError('procedure trust below compiler threshold')
        if len(card.steps) > self.global_max_steps:
            raise ValueError('procedure exceeds global step budget')
        operators: list[CognitiveOperatorSpec] = []
        capabilities = set(card.preconditions)
        total_cost = 0.0
        survival = 1.0
        for operator_id in card.steps:
            if not self.registry.has(operator_id):
                raise ValueError(f'unregistered operator step: {operator_id}')
            operator = self.registry.get(operator_id)
            missing = set(operator.requires).difference(capabilities)
            if missing:
                raise ValueError(f'capability precondition unsatisfied before {operator_id}: {sorted(missing)}')
            total_cost += float(operator.cost)
            survival *= 1.0 - float(operator.risk)
            capabilities.update(operator.provides)
            operators.append(operator)
        total_risk = 1.0 - survival
        if total_cost > float(card.max_cost) + 1e-12:
            raise ValueError('procedure cost exceeds card budget')
        if total_risk > float(card.max_risk) + 1e-12:
            raise ValueError('procedure risk exceeds card budget')
        if card.verifier_operator_id is not None:
            if card.verifier_operator_id not in card.steps:
                raise ValueError('verifier operator must be part of the procedure steps')
            if not self.registry.has(card.verifier_operator_id):
                raise ValueError('verifier operator is unregistered')
        if not set(card.expected_outputs).issubset(capabilities):
            missing = sorted(set(card.expected_outputs).difference(capabilities))
            raise ValueError(f'procedure cannot provide expected outputs: {missing}')
        return CompiledProcedure(card, tuple(operators), total_cost, total_risk, frozenset(capabilities.difference(card.preconditions)))


@dataclass
class ExternalWorkingState:
    context: dict[str, object] = field(default_factory=dict)
    capabilities: set[str] = field(default_factory=set)
    evidence: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    subgoals: list[str] = field(default_factory=list)
    representation_id: str = 'default'
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EpisodeRecord:
    objective: str
    context_tags: frozenset[str]
    procedure_ids: tuple[str, ...]
    success: bool
    outcome: str


class EpisodeMemory:
    trainable_parameter_count = 0

    def __init__(self) -> None:
        self._rows: list[EpisodeRecord] = []

    def add(self, record: EpisodeRecord) -> None:
        self._rows.append(record)

    def search(self, context_tags: Iterable[str], *, k: int = 5) -> tuple[EpisodeRecord, ...]:
        tags = set(map(str, context_tags))
        rows = sorted(
            self._rows,
            key=lambda row: (-len(tags.intersection(row.context_tags)), not row.success, row.objective, row.procedure_ids),
        )
        return tuple(rows[: max(0, int(k))])


@dataclass(frozen=True)
class CounterexampleRecord:
    procedure_id: str
    deficit_kind: str
    context_fingerprint: str
    reason: str


class CounterexampleMemory:
    trainable_parameter_count = 0

    def __init__(self) -> None:
        self._rows: list[CounterexampleRecord] = []
        self._keys: set[tuple[str, str, str]] = set()

    def add(self, procedure_id: str, deficit_kind: str, context_fingerprint: str, reason: str) -> CounterexampleRecord:
        row = CounterexampleRecord(
            _nonempty(procedure_id, 'procedure_id'),
            _nonempty(deficit_kind, 'deficit_kind'),
            _nonempty(context_fingerprint, 'context_fingerprint'),
            _nonempty(reason, 'reason'),
        )
        key = (row.procedure_id, row.deficit_kind, row.context_fingerprint)
        if key not in self._keys:
            self._keys.add(key)
            self._rows.append(row)
        return row

    def has(self, procedure_id: str, deficit_kind: str, context_fingerprint: str) -> bool:
        return (str(procedure_id), str(deficit_kind), str(context_fingerprint)) in self._keys

    def records(self) -> tuple[CounterexampleRecord, ...]:
        return tuple(self._rows)


class ProcedureCreditLedger:
    trainable_parameter_count = 0

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], list[int]] = {}

    def _row(self, procedure_id: str, deficit_kind: str) -> list[int]:
        key = (_nonempty(procedure_id, 'procedure_id'), _nonempty(deficit_kind, 'deficit_kind'))
        return self._counts.setdefault(key, [1, 1])

    def record(self, procedure_id: str, deficit_kind: str, *, success: bool) -> None:
        row = self._row(procedure_id, deficit_kind)
        row[0 if success else 1] += 1

    def competence(self, procedure_id: str, deficit_kind: str) -> float:
        success, failure = self._row(procedure_id, deficit_kind)
        return success / (success + failure)

    def counts(self, procedure_id: str, deficit_kind: str) -> tuple[int, int]:
        success, failure = self._row(procedure_id, deficit_kind)
        return success, failure


class CognitiveReflexRouter:
    trainable_parameter_count = 0

    def __init__(self, credit: ProcedureCreditLedger, counterexamples: CounterexampleMemory) -> None:
        self.credit = credit
        self.counterexamples = counterexamples

    def choose(
        self,
        procedures: Sequence[CompiledProcedure],
        *,
        deficit_kind: str,
        deficit_severity: float,
        context_tags: Iterable[str],
        context_fingerprint: str,
    ) -> CompiledProcedure:
        if not procedures:
            raise ValueError('procedures must be non-empty')
        context = set(map(str, context_tags))
        scored = []
        for procedure in procedures:
            overlap = len(context.intersection(procedure.context_tags)) / max(1, len(context.union(procedure.context_tags)))
            competence = self.credit.competence(procedure.procedure_id, deficit_kind)
            counterexample = self.counterexamples.has(procedure.procedure_id, deficit_kind, context_fingerprint)
            score = (
                1.75 * float(deficit_severity)
                + 1.4 * overlap
                + 1.2 * competence
                + 0.25 * procedure.card.trust_score
                - 0.08 * procedure.total_cost
                - 0.9 * procedure.total_risk
                - (10.0 if counterexample else 0.0)
            )
            scored.append((score, procedure))
        scored.sort(key=lambda row: (-row[0], row[1].total_cost, row[1].total_risk, row[1].procedure_id))
        return scored[0][1]


@dataclass(frozen=True)
class ReflexReceipt:
    status: str
    deficit_kind: str | None
    procedure_id: str | None
    executed_operator_ids: tuple[str, ...]
    verified: bool
    success: bool
    reason: str
    evidence: tuple[str, ...]


class CognitiveReflexRuntime:
    trainable_parameter_count = 0

    def __init__(
        self,
        *,
        detector: CognitiveDeficitDetector,
        registry: CognitiveOperatorRegistry,
        library: ProcedureLibrary,
        compiler: ProcedureCompiler,
        router: CognitiveReflexRouter,
    ) -> None:
        self.detector = detector
        self.registry = registry
        self.library = library
        self.compiler = compiler
        self.router = router

    def run_cycle(
        self,
        state: ExternalWorkingState,
        snapshot: CognitiveSnapshot,
        *,
        context_tags: Iterable[str],
        context_fingerprint: str,
    ) -> ReflexReceipt:
        deficits = self.detector.detect(snapshot)
        if not deficits:
            return ReflexReceipt('continue_reasoning', None, None, (), False, True, 'no_external_intervention_needed', ())

        # Try deficits in severity order. A lower-priority deficit with a trusted executable procedure
        # is preferable to inventing behavior for the top deficit, but if *nothing* is available we
        # explicitly request behavioral knowledge for the highest-severity deficit.
        highest = deficits[0]
        for signal in deficits:
            cards = self.library.search(signal.kind, context_tags, k=8)
            compiled: list[CompiledProcedure] = []
            for card in cards:
                try:
                    candidate = self.compiler.compile(card)
                except (ValueError, KeyError):
                    continue
                if not set(card.preconditions).issubset(state.capabilities):
                    continue
                compiled.append(candidate)
            if not compiled:
                continue
            procedure = self.router.choose(
                compiled,
                deficit_kind=signal.kind,
                deficit_severity=signal.severity,
                context_tags=context_tags,
                context_fingerprint=context_fingerprint,
            )
            if self.router.counterexamples.has(procedure.procedure_id, signal.kind, context_fingerprint):
                alternatives = [row for row in compiled if not self.router.counterexamples.has(row.procedure_id, signal.kind, context_fingerprint)]
                if not alternatives:
                    continue
                procedure = self.router.choose(
                    alternatives,
                    deficit_kind=signal.kind,
                    deficit_severity=signal.severity,
                    context_tags=context_tags,
                    context_fingerprint=context_fingerprint,
                )

            executed: list[str] = []
            evidence: list[str] = []
            verifier_success: bool | None = None
            for operator in procedure.operators:
                missing = set(operator.requires).difference(state.capabilities)
                if missing:
                    self.router.credit.record(procedure.procedure_id, signal.kind, success=False)
                    self.router.counterexamples.add(procedure.procedure_id, signal.kind, context_fingerprint, f'runtime_missing_capabilities:{sorted(missing)}')
                    return ReflexReceipt('failed', signal.kind, procedure.procedure_id, tuple(executed), False, False, 'runtime capability check failed', tuple(evidence))
                raw = dict(operator.executor(state, snapshot, signal))
                success = bool(raw.get('success', False))
                executed.append(operator.operator_id)
                updates = raw.get('updates', {})
                if updates is not None:
                    if not isinstance(updates, Mapping):
                        raise TypeError('operator updates must be a mapping')
                    state.context.update(updates)
                provided = set(operator.provides)
                provided.update(map(str, raw.get('provides', ())))
                state.capabilities.update(provided)
                evidence.extend(map(str, raw.get('evidence', ())))
                if operator.operator_id == procedure.card.verifier_operator_id:
                    verifier_success = success
                if not success:
                    reason = str(raw.get('reason', f'operator_failed:{operator.operator_id}'))
                    self.router.credit.record(procedure.procedure_id, signal.kind, success=False)
                    self.router.counterexamples.add(procedure.procedure_id, signal.kind, context_fingerprint, reason)
                    return ReflexReceipt('failed', signal.kind, procedure.procedure_id, tuple(executed), False, False, reason, tuple(evidence))

            verified = verifier_success if procedure.card.verifier_operator_id is not None else True
            success = bool(verified)
            self.router.credit.record(procedure.procedure_id, signal.kind, success=success)
            if not success:
                self.router.counterexamples.add(procedure.procedure_id, signal.kind, context_fingerprint, 'verifier_rejected')
            return ReflexReceipt('executed' if success else 'failed', signal.kind, procedure.procedure_id, tuple(executed), bool(verified), success, 'procedure_executed' if success else 'verifier_rejected', tuple(evidence))

        return ReflexReceipt(
            'acquire_behavioral_knowledge',
            highest.kind,
            None,
            (),
            False,
            False,
            'no_trusted_executable_procedure_for_detected_deficit',
            highest.evidence,
        )


def make_cognition_time_retrieval_operator(retriever, *, operator_id: str = 'knowledge.cognition_time_retrieve', query_field: str = 'knowledge_query') -> CognitiveOperatorSpec:
    """Wrap the accepted R2.1 cognition-time retriever as an R2.53 primitive operator.

    The adapter retrieves evidence from the external source and returns chunk ids/text to the
    external working state. It does not persist private model reasoning.
    """
    from .retrieval_microcycle import KnowledgeNeed

    def execute(state: ExternalWorkingState, snapshot: CognitiveSnapshot, signal: DeficitSignal):
        query = str(state.context.get(query_field, '')).strip()
        if not query:
            if snapshot.unresolved_requirements:
                query = ' '.join(map(str, snapshot.unresolved_requirements))
            else:
                query = snapshot.objective
        decision = retriever.step(KnowledgeNeed(
            query=query,
            uncertainty=max(1.0 - snapshot.evidence_coverage, 1.0 - snapshot.self_confidence, signal.severity),
            query_drift=1.0 if not retriever.state.last_query else float(query != retriever.state.last_query),
            use_anchors=bool(retriever.state.calls),
            force=signal.kind == 'knowledge_gap' and snapshot.evidence_coverage < 0.25,
        ))
        chunks = tuple(decision.chunks)
        if not decision.retrieved:
            return {
                'success': False,
                'reason': decision.reason,
                'updates': {'knowledge_retrieval_reason': decision.reason},
                'evidence': (),
                'retrieved_text': (),
                'provides': set(),
            }
        state.evidence.extend(chunk.chunk_id for chunk in chunks if chunk.chunk_id not in state.evidence)
        return {
            'success': True,
            'updates': {
                'knowledge_retrieval_reason': decision.reason,
                'knowledge_chunk_ids': tuple(chunk.chunk_id for chunk in chunks),
                'knowledge_texts': tuple(chunk.text for chunk in chunks),
            },
            'evidence': tuple(chunk.chunk_id for chunk in chunks),
            'retrieved_text': tuple(chunk.text for chunk in chunks),
            'provides': {'evidence'},
        }

    return CognitiveOperatorSpec(
        operator_id=operator_id,
        family='factual_knowledge',
        tags=frozenset({'knowledge', 'retrieval', 'cognition-time'}),
        requires=frozenset(),
        provides=frozenset({'evidence'}),
        cost=1.0,
        risk=0.01,
        side_effect_class='state_only',
        version='1',
        source_uri='nolane://r21-cognition-time-retriever',
        executor=execute,
    )
