from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, evaluate_expr, expr_digest
from .r269_causal_basis_adapter import PortableExperience
from .r269_meta_learning_kernel import (
    PublicTaskSignature,
    SharedObservation,
    SharedObservationLedger,
    _canonical_number,
    _context_key,
    match_portable_experiences,
)


@dataclass(frozen=True, slots=True)
class _Hypothesis:
    expression: Expr
    hypothesis_id: str
    origin: str
    repair_distance: int = 0


@dataclass(frozen=True, slots=True)
class MetaLearningConfig:
    max_diagnostic_queries: int = 4
    transfer_candidate_cap: int = 64
    scratch_candidate_cap: int = 256
    scratch_max_depth: int = 2
    min_scratch_partitions: int = 2

    def __post_init__(self) -> None:
        if self.max_diagnostic_queries < 1 or self.transfer_candidate_cap < 1 or self.scratch_candidate_cap < 1:
            raise ValueError('budgets must be positive')
        if self.scratch_max_depth not in (0, 1, 2):
            raise ValueError('scratch_max_depth must be 0, 1, or 2')
        if self.min_scratch_partitions < 1:
            raise ValueError('min_scratch_partitions must be positive')


@dataclass(frozen=True, slots=True)
class PriorState:
    portable_digest: str
    status: str
    contradiction_count: int
    negative_regret: int
    positive_credit: int
    reason: str


class PriorRegistry:
    def __init__(self) -> None:
        self._states: dict[str, PriorState] = {}

    @property
    def quarantined_prior_digests(self) -> frozenset[str]:
        return frozenset(k for k, v in self._states.items() if v.status == 'quarantined')

    def state_for(self, digest: str) -> PriorState:
        return self._states.get(digest, PriorState(digest, 'active', 0, 0, 0, 'unseen'))

    def quarantine(self, digest: str, *, reason: str, regret: int = 0) -> PriorState:
        old = self.state_for(digest)
        row = PriorState(
            digest,
            'quarantined',
            old.contradiction_count + 1,
            old.negative_regret + max(0, regret),
            old.positive_credit,
            reason,
        )
        self._states[digest] = row
        return row

    def credit(self, digest: str, amount: int = 1) -> PriorState:
        old = self.state_for(digest)
        row = PriorState(
            digest,
            old.status,
            old.contradiction_count,
            old.negative_regret,
            old.positive_credit + max(0, amount),
            'verified_credit',
        )
        self._states[digest] = row
        return row


@dataclass(frozen=True, slots=True)
class MetaLearningReceipt:
    passed: bool
    mode: str
    selected_expression: Expr | None
    selected_prior_digest: str | None
    physical_diagnostic_calls: int
    physical_terminal_calls: int
    transfer_candidates_considered: int
    scratch_candidates_considered: int
    reused_observations: int
    avoided_duplicate_calls: int
    transfer_contradictions: int
    quarantine_action: bool
    false_accepts: int
    reason: str
    ledger: tuple[SharedObservation, ...]
    trainable_parameter_count: int = 0

    def __post_init__(self) -> None:
        if self.trainable_parameter_count != 0:
            raise ValueError('trainable_parameter_count must remain zero')
        if self.false_accepts != 0:
            raise ValueError('R2.69 receipts cannot authorize false accepts')


def _rewrite(expr: Expr, mapping: Mapping[str, str]) -> Expr:
    if isinstance(expr, Field):
        return Field(mapping.get(expr.name, expr.name))
    if isinstance(expr, Const):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _rewrite(expr.arg, mapping))
    if isinstance(expr, Binary):
        return Binary(expr.op, _rewrite(expr.left, mapping), _rewrite(expr.right, mapping))
    if isinstance(expr, IfElse):
        return IfElse(
            _rewrite(expr.condition, mapping),
            _rewrite(expr.when_true, mapping),
            _rewrite(expr.when_false, mapping),
        )
    raise TypeError(type(expr).__name__)


def _mutations(expr: Expr, ops: Sequence[str]) -> tuple[Expr, ...]:
    out: list[Expr] = []
    if isinstance(expr, Binary):
        out.extend(Binary(op, expr.left, expr.right) for op in ops if op != expr.op)
        out.extend(Binary(expr.op, child, expr.right) for child in _mutations(expr.left, ops))
        out.extend(Binary(expr.op, expr.left, child) for child in _mutations(expr.right, ops))
    elif isinstance(expr, Unary):
        out.extend(Unary(expr.op, child) for child in _mutations(expr.arg, ops))
    elif isinstance(expr, IfElse):
        out.extend(IfElse(child, expr.when_true, expr.when_false) for child in _mutations(expr.condition, ops))
        out.extend(IfElse(expr.condition, child, expr.when_false) for child in _mutations(expr.when_true, ops))
        out.extend(IfElse(expr.condition, expr.when_true, child) for child in _mutations(expr.when_false, ops))
    return tuple(out)


def _structural_key(expr: Expr) -> str:
    if isinstance(expr, Field):
        return json.dumps(('f', expr.name), separators=(',', ':'))
    if isinstance(expr, Const):
        return json.dumps(('c', expr.value), separators=(',', ':'))
    if isinstance(expr, Unary):
        return json.dumps(('u', expr.op, _structural_key(expr.arg)), separators=(',', ':'))
    if isinstance(expr, Binary):
        left = _structural_key(expr.left)
        right = _structural_key(expr.right)
        # Only universally valid finite-numeric identities are proof authority.
        # Finite agreement on the current diagnostic corpus is not enough.
        if expr.op in ('min', 'max') and left == right:
            return left
        if expr.op in ('add', 'mul', 'min', 'max') and right < left:
            left, right = right, left
        return json.dumps(('b', expr.op, left, right), separators=(',', ':'))
    if isinstance(expr, IfElse):
        return json.dumps(
            ('i', _structural_key(expr.condition), _structural_key(expr.when_true), _structural_key(expr.when_false)),
            separators=(',', ':'),
        )
    raise TypeError(type(expr).__name__)


def _dedupe(rows: Sequence[_Hypothesis], cap: int) -> list[_Hypothesis]:
    by: dict[str, _Hypothesis] = {}
    for row in rows:
        key = _structural_key(row.expression)
        old = by.get(key)
        if old is None or (row.repair_distance, row.hypothesis_id) < (old.repair_distance, old.hypothesis_id):
            by[key] = row
    return sorted(by.values(), key=lambda r: (r.repair_distance, r.hypothesis_id))[:cap]


def _transfer_hypotheses(portable: PortableExperience, sig: PublicTaskSignature, cap: int) -> list[_Hypothesis]:
    bases = [(portable.canonical_expression, 0)] + [
        (expr, 1) for expr in _mutations(portable.canonical_expression, sig.allowed_binary_ops)
    ]
    rows: list[_Hypothesis] = []
    for expr, distance in bases:
        for permutation in itertools.permutations(sig.role_names):
            rewritten = _rewrite(expr, dict(zip(portable.canonical_roles, permutation, strict=True)))
            rows.append(_Hypothesis(rewritten, 'transfer.' + expr_digest(rewritten), 'transfer', distance))
    return _dedupe(rows, cap)


def _scratch_hypotheses(sig: PublicTaskSignature, cfg: MetaLearningConfig) -> list[_Hypothesis]:
    rows: list[_Hypothesis] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        key = _structural_key(expr)
        if key in seen:
            return True
        seen.add(key)
        rows.append(_Hypothesis(expr, 'scratch.' + expr_digest(expr), 'scratch', len(rows)))
        return len(rows) < cfg.scratch_candidate_cap

    fields = tuple(Field(name) for name in sig.role_names)
    for field in fields:
        if not add(field):
            return rows
    if cfg.scratch_max_depth == 0:
        return rows

    level1: list[Expr] = []
    for op in sig.allowed_binary_ops:
        for left in fields:
            for right in fields:
                expr = Binary(op, left, right)
                level1.append(expr)
                if not add(expr):
                    return rows
    if cfg.scratch_max_depth == 1:
        return rows

    for op in sig.allowed_binary_ops:
        for nested in level1:
            for field in fields:
                if not add(Binary(op, nested, field)):
                    return rows
                if not add(Binary(op, field, nested)):
                    return rows
    return rows


def _predict(expr: Expr, context: Mapping[str, object]) -> tuple[bool, int | float | None]:
    try:
        return True, _canonical_number(evaluate_expr(expr, context))
    except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False, None


def _partitions(rows: Sequence[_Hypothesis], context: Mapping[str, object]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        ok, value = _predict(row.expression, context)
        key = 'invalid' if not ok else json.dumps(value, separators=(',', ':'), allow_nan=False)
        out[key] = out.get(key, 0) + 1
    return out


def _choose_query(
    transfer: Sequence[_Hypothesis],
    scratch: Sequence[_Hypothesis],
    contexts: Sequence[Mapping[str, object]],
    used: frozenset[str],
    signature: PublicTaskSignature,
    min_scratch_partitions: int,
):
    transfer_best = None
    scratch_best = None
    for context in contexts:
        key = _context_key(signature, context)
        if key in used:
            continue
        transfer_parts = _partitions(transfer, context) if transfer else {}
        scratch_parts = _partitions(scratch, context) if scratch else {}
        transfer_info = len(transfer_parts)
        scratch_info = len(scratch_parts)
        if len(transfer) > 1 and transfer_info > 1 and scratch_info >= min_scratch_partitions:
            score = (max(transfer_parts.values()), max(scratch_parts.values()), -transfer_info, -scratch_info, key)
            if transfer_best is None or score < transfer_best[0]:
                transfer_best = (score, context, transfer_info, scratch_info)
        if len(scratch) > 1 and scratch_info > 1:
            score = (max(scratch_parts.values()), -scratch_info, key)
            if scratch_best is None or score < scratch_best[0]:
                scratch_best = (score, context, transfer_info, scratch_info)
    if transfer_best is not None:
        return transfer_best[1], transfer_best[2], transfer_best[3], 'transfer'
    if scratch_best is not None:
        return scratch_best[1], scratch_best[2], scratch_best[3], 'scratch'
    return None, 0, 0, 'scratch'


def _filter(rows: Sequence[_Hypothesis], context: Mapping[str, object], observed: int | float) -> list[_Hypothesis]:
    return [row for row in rows if (lambda pred: pred[0] and pred[1] == observed)(_predict(row.expression, context))]


def _terminal_verify(selected: _Hypothesis, terminal_contexts, oracle, ledger: SharedObservationLedger):
    before = ledger.physical_oracle_calls
    for context in terminal_contexts:
        try:
            row, _ = ledger.observe(
                context,
                oracle,
                phase='terminal',
                provenance='shared',
                transfer_info_score=0,
                scratch_info_score=0,
            )
        except ValueError:
            return False, 'terminal_evidence_overlap', ledger.physical_oracle_calls - before
        if row.status != 'ok':
            return False, row.status, ledger.physical_oracle_calls - before
        semantic = dict(zip(ledger.signature.role_names, row.context_values, strict=True))
        ok, predicted = _predict(selected.expression, semantic)
        if not ok or predicted != row.observed:
            return False, 'terminal_contradiction', ledger.physical_oracle_calls - before
    return True, 'verified', ledger.physical_oracle_calls - before


def run_meta_learning_episode(
    priors,
    signature,
    diagnostic_contexts,
    terminal_contexts,
    oracle,
    config,
    *,
    registry=None,
) -> MetaLearningReceipt:
    if not isinstance(config, MetaLearningConfig):
        raise TypeError('config must be MetaLearningConfig')
    if not diagnostic_contexts or not terminal_contexts:
        raise ValueError('diagnostic and terminal contexts must be non-empty')
    diagnostic_keys = tuple(_context_key(signature, row) for row in diagnostic_contexts)
    terminal_keys = tuple(_context_key(signature, row) for row in terminal_contexts)
    if len(set(diagnostic_keys)) != len(diagnostic_keys) or len(set(terminal_keys)) != len(terminal_keys):
        raise ValueError('contexts must be semantically unique')
    if set(diagnostic_keys) & set(terminal_keys):
        raise ValueError('diagnostic and terminal contexts must be semantically disjoint')

    registry = registry if registry is not None else PriorRegistry()
    matches = match_portable_experiences(
        priors,
        signature,
        quarantined_prior_digests=registry.quarantined_prior_digests,
    )
    compatible = [row.portable for row in matches if row.compatible]
    prior = compatible[0] if compatible else None
    transfer = _transfer_hypotheses(prior, signature, config.transfer_candidate_cap) if prior else []
    scratch = _scratch_hypotheses(signature, config)
    transfer_initial = len(transfer)
    scratch_initial = len(scratch)
    ledger = SharedObservationLedger(signature)
    used: set[str] = set()
    abandoned = False
    contradictions = 0
    quarantine = False
    reused_count = 0

    for _ in range(config.max_diagnostic_queries):
        if len(transfer) == 1 and ledger.physical_oracle_calls >= 1:
            break
        if not transfer and len(scratch) == 1 and ledger.physical_oracle_calls >= 1:
            break
        context, transfer_info, scratch_info, provenance = _choose_query(
            transfer,
            scratch,
            diagnostic_contexts,
            frozenset(used),
            signature,
            config.min_scratch_partitions,
        )
        if context is None:
            break
        key = _context_key(signature, context)
        row, reused = ledger.observe(
            context,
            oracle,
            phase='diagnostic',
            provenance=provenance,
            transfer_info_score=transfer_info,
            scratch_info_score=scratch_info,
        )
        used.add(key)
        reused_count += int(reused)
        if row.status != 'ok' or row.observed is None:
            if prior:
                registry.quarantine(prior.portable_digest, reason=row.status, regret=1)
                quarantine = True
            return MetaLearningReceipt(
                False,
                'transfer' if prior else 'scratch',
                None,
                prior.portable_digest if prior else None,
                sum(ob.phase == 'diagnostic' for ob in ledger.observations),
                0,
                transfer_initial,
                scratch_initial,
                reused_count,
                reused_count,
                contradictions,
                quarantine,
                0,
                row.status,
                ledger.observations,
            )
        semantic = dict(zip(signature.role_names, row.context_values, strict=True))
        if transfer:
            transfer = _filter(transfer, semantic, row.observed)
            if not transfer and prior:
                contradictions += 1
                abandoned = True
                reused_count = sum(ob.phase == 'diagnostic' for ob in ledger.observations)
                registry.quarantine(prior.portable_digest, reason='transfer_hypothesis_eliminated', regret=1)
                quarantine = True
        scratch = _filter(scratch, semantic, row.observed)

    selected = None
    mode = 'scratch'
    if len(transfer) == 1 and ledger.physical_oracle_calls >= 1:
        selected = transfer[0]
        mode = 'transfer'
    elif len(scratch) == 1 and ledger.physical_oracle_calls >= 1:
        selected = scratch[0]
        mode = 'scratch_after_transfer' if abandoned else 'scratch'

    if selected is None:
        return MetaLearningReceipt(
            False,
            'scratch_after_transfer' if abandoned else ('transfer' if prior else 'scratch'),
            None,
            prior.portable_digest if prior else None,
            sum(ob.phase == 'diagnostic' for ob in ledger.observations),
            0,
            transfer_initial,
            scratch_initial,
            reused_count,
            reused_count,
            contradictions,
            quarantine,
            0,
            'diagnostic_ambiguity',
            ledger.observations,
        )

    passed, reason, terminal_calls = _terminal_verify(selected, terminal_contexts, oracle, ledger)
    if not passed:
        if mode == 'transfer' and prior:
            registry.quarantine(prior.portable_digest, reason=reason, regret=terminal_calls)
            quarantine = True
        return MetaLearningReceipt(
            False,
            mode,
            None,
            prior.portable_digest if prior else None,
            sum(ob.phase == 'diagnostic' for ob in ledger.observations),
            terminal_calls,
            transfer_initial,
            scratch_initial,
            reused_count,
            reused_count,
            contradictions,
            quarantine,
            0,
            reason,
            ledger.observations,
        )

    reason = (
        'accepted_transfer'
        if mode == 'transfer'
        else ('accepted_scratch_after_transfer' if mode == 'scratch_after_transfer' else 'accepted_scratch')
    )
    return MetaLearningReceipt(
        True,
        mode,
        selected.expression,
        prior.portable_digest if mode == 'transfer' and prior else None,
        sum(ob.phase == 'diagnostic' for ob in ledger.observations),
        terminal_calls,
        transfer_initial,
        scratch_initial,
        reused_count,
        reused_count,
        contradictions,
        quarantine,
        0,
        reason,
        ledger.observations,
    )


def run_cold_scratch(signature, diagnostic_contexts, terminal_contexts, oracle, config) -> MetaLearningReceipt:
    return run_meta_learning_episode((), signature, diagnostic_contexts, terminal_contexts, oracle, config)


__all__ = [
    'MetaLearningConfig',
    'PriorState',
    'PriorRegistry',
    'MetaLearningReceipt',
    'run_meta_learning_episode',
    'run_cold_scratch',
]
