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
    prior_digests: tuple[str, ...] = ()


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
        if self.scratch_max_depth not in (0, 1, 2, 3):
            raise ValueError('scratch_max_depth must be 0, 1, 2, or 3')
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
        return frozenset(digest for digest, state in self._states.items() if state.status == 'quarantined')

    def state_for(self, digest: str) -> PriorState:
        return self._states.get(str(digest), PriorState(str(digest), 'active', 0, 0, 0, 'unseen'))

    def quarantine(self, digest: str, *, reason: str, regret: int = 0) -> PriorState:
        old = self.state_for(digest)
        row = PriorState(
            str(digest),
            'quarantined',
            old.contradiction_count + 1,
            old.negative_regret + max(0, int(regret)),
            old.positive_credit,
            str(reason),
        )
        self._states[row.portable_digest] = row
        return row

    def credit(self, digest: str, amount: int = 1) -> PriorState:
        old = self.state_for(digest)
        row = PriorState(
            str(digest),
            old.status,
            old.contradiction_count,
            old.negative_regret,
            old.positive_credit + max(0, int(amount)),
            'verified_credit',
        )
        self._states[row.portable_digest] = row
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
        if any(value < 0 for value in (
            self.physical_diagnostic_calls,
            self.physical_terminal_calls,
            self.transfer_candidates_considered,
            self.scratch_candidates_considered,
            self.reused_observations,
            self.avoided_duplicate_calls,
            self.transfer_contradictions,
        )):
            raise ValueError('receipt counters must be non-negative')


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
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


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


def _finite_integer_semantic_key(expr: Expr, signature: PublicTaskSignature) -> str:
    if signature.numeric_domain != 'finite_integer':
        raise ValueError('complete finite-domain proof requires finite_integer signature')
    rows: list[tuple[str, object]] = []
    for values in itertools.product(signature.finite_integer_values, repeat=len(signature.role_names)):
        context = dict(zip(signature.role_names, values, strict=True))
        try:
            value = _canonical_number(evaluate_expr(expr, context))
            if not isinstance(value, int):
                rows.append(('invalid', 'non_integer'))
            else:
                rows.append(('value', value))
        except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            rows.append(('invalid', 'evaluation'))
    # Because finite_integer_values declares the complete legal query universe,
    # this vector is an extensional proof inside the bounded Phase-A domain,
    # not a finite sampled fingerprint.
    return json.dumps(('finite-extensional-proof', rows), separators=(',', ':'))


def _structural_key(expr: Expr, signature: PublicTaskSignature) -> str:
    if signature.numeric_domain == 'finite_integer':
        return _finite_integer_semantic_key(expr, signature)
    if isinstance(expr, Field):
        return json.dumps(('f', expr.name), separators=(',', ':'))
    if isinstance(expr, Const):
        return json.dumps(('c', expr.value), separators=(',', ':'))
    if isinstance(expr, Unary):
        return json.dumps(('u', expr.op, _structural_key(expr.arg, signature)), separators=(',', ':'))
    if isinstance(expr, Binary):
        left = _structural_key(expr.left, signature)
        right = _structural_key(expr.right, signature)
        if expr.op in ('min', 'max') and left == right:
            return left
        if expr.op in ('add', 'mul', 'min', 'max') and right < left:
            left, right = right, left
        return json.dumps(('b', expr.op, left, right), separators=(',', ':'))
    if isinstance(expr, IfElse):
        return json.dumps(
            (
                'i',
                _structural_key(expr.condition, signature),
                _structural_key(expr.when_true, signature),
                _structural_key(expr.when_false, signature),
            ),
            separators=(',', ':'),
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _dedupe(rows: Sequence[_Hypothesis], cap: int, signature: PublicTaskSignature) -> list[_Hypothesis]:
    by_key: dict[str, _Hypothesis] = {}
    contributors: dict[str, set[str]] = {}
    for row in rows:
        key = _structural_key(row.expression, signature)
        contributors.setdefault(key, set()).update(row.prior_digests)
        old = by_key.get(key)
        if old is None or (row.repair_distance, row.hypothesis_id) < (old.repair_distance, old.hypothesis_id):
            by_key[key] = row
    merged = [
        _Hypothesis(
            row.expression,
            row.hypothesis_id,
            row.origin,
            row.repair_distance,
            tuple(sorted(contributors[key])),
        )
        for key, row in by_key.items()
    ]
    return sorted(merged, key=lambda row: (row.repair_distance, row.hypothesis_id))[:int(cap)]


def _transfer_hypotheses(portable: PortableExperience, signature: PublicTaskSignature, cap: int) -> list[_Hypothesis]:
    bases = [(portable.canonical_expression, 0)] + [
        (expr, 1) for expr in _mutations(portable.canonical_expression, signature.allowed_binary_ops)
    ]
    rows: list[_Hypothesis] = []
    for expr, distance in bases:
        for permutation in itertools.permutations(signature.role_names):
            rewritten = _rewrite(expr, dict(zip(portable.canonical_roles, permutation, strict=True)))
            rows.append(
                _Hypothesis(
                    rewritten,
                    'transfer.' + expr_digest(rewritten),
                    'transfer',
                    distance,
                    (portable.portable_digest,),
                )
            )
    return _dedupe(rows, int(cap), signature)


def _transfer_hypotheses_many(
    portables: Sequence[PortableExperience],
    signature: PublicTaskSignature,
    cap: int,
) -> list[_Hypothesis]:
    if not portables:
        return []
    # Each compatible prior gets an equal opportunity to contribute at each
    # ranked position.  This keeps the total cap proof-distinct and prevents a
    # syntactically prolific prior from starving another before target evidence.
    per_prior = [
        _transfer_hypotheses(portable, signature, int(cap))
        for portable in sorted(portables, key=lambda row: row.portable_digest)
    ]
    interleaved: list[_Hypothesis] = []
    max_len = max(map(len, per_prior), default=0)
    for index in range(max_len):
        for rows in per_prior:
            if index < len(rows):
                interleaved.append(rows[index])
    return _dedupe(interleaved, int(cap), signature)


def _prior_digests(rows: Sequence[_Hypothesis]) -> frozenset[str]:
    return frozenset(digest for row in rows for digest in row.prior_digests)


def _scratch_hypotheses(signature: PublicTaskSignature, config: MetaLearningConfig) -> list[_Hypothesis]:
    rows: list[_Hypothesis] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        key = _structural_key(expr, signature)
        if key in seen:
            return True
        seen.add(key)
        rows.append(_Hypothesis(expr, 'scratch.' + expr_digest(expr), 'scratch', len(rows)))
        return len(rows) < config.scratch_candidate_cap

    fields = tuple(Field(name) for name in signature.role_names)
    for field in fields:
        if not add(field):
            return rows
    if config.scratch_max_depth == 0:
        return rows

    level1: list[Expr] = []
    for op in signature.allowed_binary_ops:
        for left in fields:
            for right in fields:
                expr = Binary(op, left, right)
                level1.append(expr)
                if not add(expr):
                    return rows
    if config.scratch_max_depth == 1:
        return rows

    for op in signature.allowed_binary_ops:
        for nested in level1:
            for field in fields:
                if not add(Binary(op, nested, field)):
                    return rows
                if not add(Binary(op, field, nested)):
                    return rows
    if config.scratch_max_depth == 2:
        return rows

    # In a declared complete finite-integer universe, admit balanced depth-2
    # compositions before expanding to depth 3. This prevents the candidate
    # cap from starving simple four-role programs such as (a+b)-(c+d). The
    # support-disjoint/full-cover gate keeps this bounded, and extensional
    # deduplication above is proof-authoritative over the complete domain.
    if signature.numeric_domain == 'finite_integer':
        role_set = frozenset(signature.role_names)

        def support(expr: Expr) -> frozenset[str]:
            if isinstance(expr, Field):
                return frozenset((expr.name,))
            if isinstance(expr, Const):
                return frozenset()
            if isinstance(expr, Unary):
                return support(expr.arg)
            if isinstance(expr, Binary):
                return support(expr.left) | support(expr.right)
            if isinstance(expr, IfElse):
                return support(expr.condition) | support(expr.when_true) | support(expr.when_false)
            raise TypeError(f'unsupported expression type: {type(expr).__name__}')

        balanced_atoms = tuple(row.expression for row in rows if row.expression.depth == 1)
        support_by_digest = {expr_digest(expr): support(expr) for expr in balanced_atoms}
        for op in signature.allowed_binary_ops:
            for left in balanced_atoms:
                left_support = support_by_digest[expr_digest(left)]
                for right in balanced_atoms:
                    right_support = support_by_digest[expr_digest(right)]
                    if left_support & right_support:
                        continue
                    if left_support | right_support != role_set:
                        continue
                    if not add(Binary(op, left, right)):
                        return rows

    # Depth 3 is reserved for the roomy expressibility control. Proposal
    # ordering up through the tight baseline is unchanged; the exact-domain
    # balanced layer above is admitted only for roomy depth-3 search.
    previous = tuple(row.expression for row in rows)
    frontier = tuple(expr for expr in previous if expr.depth == 2)
    lower = tuple(expr for expr in previous if expr.depth <= 2)
    for op in signature.allowed_binary_ops:
        for left in frontier:
            for right in lower:
                if not add(Binary(op, left, right)):
                    return rows
                if right is not left and not add(Binary(op, right, left)):
                    return rows
    return rows


def _scratch_information_floor(
    signature: PublicTaskSignature,
    config: MetaLearningConfig,
) -> list[_Hypothesis]:
    """Materialize only a bounded shallow scratch sentinel for transfer-query safety.

    Sentinel hypotheses may score whether a transfer probe also partitions a
    generic scratch space, but they are never selection authority. Full scratch
    is materialized only for cold scratch or after transfer is abandoned.
    """
    floor_config = MetaLearningConfig(
        max_diagnostic_queries=config.max_diagnostic_queries,
        transfer_candidate_cap=config.transfer_candidate_cap,
        scratch_candidate_cap=min(config.scratch_candidate_cap, 32),
        scratch_max_depth=min(config.scratch_max_depth, 1),
        min_scratch_partitions=config.min_scratch_partitions,
    )
    return _scratch_hypotheses(signature, floor_config)


def _predict(expr: Expr, context: Mapping[str, object]) -> tuple[bool, int | float | None]:
    try:
        return True, _canonical_number(evaluate_expr(expr, context))
    except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False, None


def _partitions(rows: Sequence[_Hypothesis], context: Mapping[str, object]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        valid, value = _predict(row.expression, context)
        key = 'invalid' if not valid else json.dumps(value, separators=(',', ':'), allow_nan=False)
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
    survivors: list[_Hypothesis] = []
    for row in rows:
        valid, predicted = _predict(row.expression, context)
        if valid and predicted == observed:
            survivors.append(row)
    return survivors


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
        valid, predicted = _predict(selected.expression, semantic)
        if not valid or predicted != row.observed:
            return False, 'terminal_contradiction', ledger.physical_oracle_calls - before
    return True, 'verified', ledger.physical_oracle_calls - before


def _receipt(
    passed: bool,
    mode: str,
    selected: Expr | None,
    prior_digest: str | None,
    ledger: SharedObservationLedger,
    transfer_initial: int,
    scratch_initial: int,
    reused: int,
    contradictions: int,
    quarantine: bool,
    reason: str,
    terminal_calls: int = 0,
) -> MetaLearningReceipt:
    return MetaLearningReceipt(
        passed=passed,
        mode=mode,
        selected_expression=selected,
        selected_prior_digest=prior_digest,
        physical_diagnostic_calls=sum(row.phase == 'diagnostic' for row in ledger.observations),
        physical_terminal_calls=terminal_calls,
        transfer_candidates_considered=transfer_initial,
        scratch_candidates_considered=scratch_initial,
        reused_observations=reused,
        avoided_duplicate_calls=reused,
        transfer_contradictions=contradictions,
        quarantine_action=quarantine,
        false_accepts=0,
        reason=reason,
        ledger=ledger.observations,
        trainable_parameter_count=0,
    )


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
    if not isinstance(signature, PublicTaskSignature):
        raise TypeError('signature must be PublicTaskSignature')
    if not isinstance(config, MetaLearningConfig):
        raise TypeError('config must be MetaLearningConfig')
    if not callable(oracle):
        raise TypeError('oracle must be callable')
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
    compatible_matches = [row for row in matches if row.compatible]
    compatible = [row.portable for row in compatible_matches]
    single_prior_digest = compatible[0].portable_digest if len(compatible) == 1 else None
    match_score_by_digest = {
        row.portable.portable_digest: row.compatibility_score for row in compatible_matches
    }
    transfer = _transfer_hypotheses_many(compatible, signature, config.transfer_candidate_cap)
    transfer_initial = len(transfer)
    scratch_materialized = not bool(transfer)
    scratch = (
        _scratch_hypotheses(signature, config)
        if scratch_materialized
        else _scratch_information_floor(signature, config)
    )
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
            # Oracle/process failures are not evidence that any particular prior
            # is wrong.  Fail closed without poisoning reusable prior state.
            return _receipt(
                False,
                'transfer' if compatible else 'scratch',
                None,
                single_prior_digest,
                ledger,
                transfer_initial,
                scratch_initial,
                reused_count,
                contradictions,
                quarantine,
                row.status,
            )

        semantic = dict(zip(signature.role_names, row.context_values, strict=True))
        if transfer:
            before_priors = _prior_digests(transfer)
            transfer = _filter(transfer, semantic, row.observed)
            after_priors = _prior_digests(transfer)
            eliminated_priors = before_priors - after_priors
            for digest in sorted(eliminated_priors):
                registry.quarantine(digest, reason='transfer_hypothesis_eliminated', regret=0)
            if eliminated_priors:
                quarantine = True
            if not transfer and before_priors:
                contradictions += 1
                abandoned = True
                # All already purchased diagnostic observations are eligible for
                # scratch continuation. This is the concrete shared-evidence
                # credit, not an extra oracle call. Only now do we materialize
                # the full scratch frontier and replay already purchased evidence.
                reused_count = sum(observation.phase == 'diagnostic' for observation in ledger.observations)
                full_scratch = _scratch_hypotheses(signature, config)
                scratch_initial = len(full_scratch)
                scratch = full_scratch
                scratch_materialized = True
                for observation in ledger.observations:
                    if (
                        observation.phase != 'diagnostic'
                        or observation.status != 'ok'
                        or observation.observed is None
                    ):
                        continue
                    observed_context = dict(
                        zip(signature.role_names, observation.context_values, strict=True)
                    )
                    scratch = _filter(scratch, observed_context, observation.observed)
                continue
        scratch = _filter(scratch, semantic, row.observed)

    selected: _Hypothesis | None = None
    mode = 'scratch'
    if len(transfer) == 1 and ledger.physical_oracle_calls >= 1:
        selected = transfer[0]
        mode = 'transfer'
    elif scratch_materialized and len(scratch) == 1 and ledger.physical_oracle_calls >= 1:
        selected = scratch[0]
        mode = 'scratch_after_transfer' if abandoned else 'scratch'

    selected_prior_digest: str | None = None
    if selected is not None and mode == 'transfer' and selected.prior_digests:
        selected_prior_digest = sorted(
            selected.prior_digests,
            key=lambda digest: (-match_score_by_digest.get(digest, 0), digest),
        )[0]

    if selected is None:
        return _receipt(
            False,
            'scratch_after_transfer' if abandoned else ('transfer' if compatible else 'scratch'),
            None,
            single_prior_digest,
            ledger,
            transfer_initial,
            scratch_initial,
            reused_count,
            contradictions,
            quarantine,
            'diagnostic_ambiguity',
        )

    passed, terminal_reason, terminal_calls = _terminal_verify(selected, terminal_contexts, oracle, ledger)
    if not passed:
        if mode == 'transfer':
            for digest in selected.prior_digests:
                registry.quarantine(digest, reason=terminal_reason, regret=terminal_calls)
                quarantine = True
        return _receipt(
            False,
            mode,
            None,
            selected_prior_digest,
            ledger,
            transfer_initial,
            scratch_initial,
            reused_count,
            contradictions,
            quarantine,
            terminal_reason,
            terminal_calls,
        )

    reason = (
        'accepted_transfer'
        if mode == 'transfer'
        else ('accepted_scratch_after_transfer' if mode == 'scratch_after_transfer' else 'accepted_scratch')
    )
    return _receipt(
        True,
        mode,
        selected.expression,
        selected_prior_digest,
        ledger,
        transfer_initial,
        scratch_initial,
        reused_count,
        contradictions,
        quarantine,
        reason,
        terminal_calls,
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
