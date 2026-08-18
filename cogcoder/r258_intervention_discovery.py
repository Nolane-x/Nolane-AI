from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary import AbstractionCall, CognitiveVocabulary, TemplateParam, evaluate_with_vocabulary
from .r257_vocabulary_synthesis import synthesize_base_with_budget, synthesize_with_vocabulary


@dataclass(frozen=True, slots=True)
class PositionalSchema:
    field_names: tuple[str, ...]

    def __post_init__(self) -> None:
        fields = tuple(str(value).strip() for value in self.field_names)
        if not fields or any(not value for value in fields):
            raise ValueError('field_names must be non-empty strings')
        if len(set(fields)) != len(fields):
            raise ValueError('field_names must be distinct')
        object.__setattr__(self, 'field_names', fields)

    @property
    def canonical_fields(self) -> tuple[str, ...]:
        return tuple(f'__f{index}' for index in range(len(self.field_names)))

    def to_canonical_context(self, context: Mapping[str, object]) -> dict[str, object]:
        missing = [field for field in self.field_names if field not in context]
        if missing:
            raise KeyError(f'missing schema fields: {missing}')
        return {canonical: context[field] for field, canonical in zip(self.field_names, self.canonical_fields, strict=True)}

    @staticmethod
    def _rewrite_expr(expr: Expr, mapping: Mapping[str, str]) -> Expr:
        def walk(node: Expr) -> Expr:
            if isinstance(node, Field):
                try:
                    return Field(mapping[node.name])
                except KeyError:
                    raise ValueError(f'unknown schema field: {node.name}') from None
            if isinstance(node, Const):
                return node
            if isinstance(node, Unary):
                return Unary(node.op, walk(node.arg))
            if isinstance(node, Binary):
                return Binary(node.op, walk(node.left), walk(node.right))
            if isinstance(node, IfElse):
                return IfElse(walk(node.condition), walk(node.when_true), walk(node.when_false))
            if isinstance(node, AbstractionCall):
                return AbstractionCall(node.abstraction_id, tuple(walk(arg) for arg in node.args))
            if isinstance(node, TemplateParam):
                return node
            raise TypeError(f'unsupported expression node: {type(node).__name__}')
        return walk(expr)

    def externalize_expr(self, expr: Expr) -> Expr:
        mapping = dict(zip(self.canonical_fields, self.field_names, strict=True))
        return self._rewrite_expr(expr, mapping)

    def canonicalize_expr(self, expr: Expr) -> Expr:
        mapping = dict(zip(self.field_names, self.canonical_fields, strict=True))
        return self._rewrite_expr(expr, mapping)


@dataclass(frozen=True, slots=True)
class InterventionSpec:
    """A pure positional rewrite over an ordered input field tuple.

    The content identity is deliberately independent of field names. Semantic names are
    resolved only when the intervention is executed against a concrete ordered schema.
    """

    bindings: tuple[tuple[int, float], ...]

    def __post_init__(self) -> None:
        normalized: list[tuple[int, float]] = []
        for position, value in tuple(self.bindings):
            position = int(position)
            value = float(value)
            if position < 0:
                raise ValueError('intervention positions must be non-negative')
            if not math.isfinite(value):
                raise ValueError('intervention values must be finite')
            normalized.append((position, value))
        if not normalized:
            raise ValueError('intervention must contain at least one binding')
        positions = [position for position, _value in normalized]
        if len(positions) != len(set(positions)):
            raise ValueError('intervention positions must be distinct')
        values = [value for _position, value in normalized]
        if len(values) != len(set(values)):
            raise ValueError('intervention anchor values must be distinct')
        object.__setattr__(self, 'bindings', tuple(normalized))

    @property
    def intervention_id(self) -> str:
        raw = json.dumps(
            {'bindings': [[position, value] for position, value in self.bindings]},
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
        )
        return f'intv.{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'

    def bind(self, field_names: Sequence[str]) -> tuple[tuple[str, float], ...]:
        fields = tuple(map(str, field_names))
        if not fields:
            raise ValueError('field_names must be non-empty')
        out: list[tuple[str, float]] = []
        for position, value in self.bindings:
            if position >= len(fields):
                raise ValueError('intervention position out of range')
            out.append((fields[position], value))
        return tuple(out)

    def apply(self, context: Mapping[str, object], field_names: Sequence[str]) -> dict[str, object]:
        out = dict(context)
        for field, value in self.bind(field_names):
            if field not in out:
                raise KeyError(field)
            out[field] = value
        return out


def enumerate_interventions(
    field_names: Sequence[str],
    anchor_values: Sequence[float],
    *,
    arity: int = 2,
) -> tuple[InterventionSpec, ...]:
    fields = tuple(map(str, field_names))
    if not fields or any(not value.strip() for value in fields):
        raise ValueError('field_names must be non-empty strings')
    if len(set(fields)) != len(fields):
        raise ValueError('field_names must be distinct')
    arity = int(arity)
    if arity < 1:
        raise ValueError('arity must be positive')
    if arity > len(fields):
        return ()
    anchors = tuple(float(value) for value in anchor_values)
    if any(not math.isfinite(value) for value in anchors):
        raise ValueError('anchor_values must be finite')
    anchors = tuple(dict.fromkeys(anchors))
    if arity > len(anchors):
        return ()

    rows: list[InterventionSpec] = []
    for positions in itertools.combinations(range(len(fields)), arity):
        for values in itertools.permutations(anchors, arity):
            rows.append(InterventionSpec(tuple(zip(positions, values, strict=True))))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class InterventionCandidateReceipt:
    intervention: InterventionSpec
    passed: bool
    reason: str
    base_probe_passed: bool = False
    vocabulary_probe_passed: bool = False
    probe_expression: Expr | None = None
    probe_candidates_considered: int = 0
    probe_validation_cases: int = 0
    probe_validation_exact: int = 0
    probe_oracle_calls: int = 0
    validation_oracle_calls: int = 0
    seeded_downstream_passed: bool = False
    seeded_downstream_candidates_considered: int = 0
    used_abstraction_ids: tuple[str, ...] = ()
    seeded_downstream_expression: Expr | None = None


@dataclass(frozen=True, slots=True)
class InterventionDiscoveryReceipt:
    passed: bool
    selected: InterventionCandidateReceipt | None
    candidates: tuple[InterventionCandidateReceipt, ...]
    no_seed_passed: bool
    no_seed_candidates_considered: int
    oracle_calls: int
    reason: str
    trainable_parameter_count: int = 0


def _equivalent(actual: object, expected: object) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False
    return actual == expected


def _oracle_value(oracle: Callable[[Mapping[str, object]], object], context: Mapping[str, object]) -> object:
    value = oracle(dict(context))
    try:
        json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError('oracle outputs must be finite JSON-compatible values') from exc
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('oracle outputs must be finite')
    return value


def _output_key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def discover_causal_intervention(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    probe_training_contexts: Sequence[Mapping[str, object]],
    probe_validation_contexts: Sequence[Mapping[str, object]],
    vocabulary: CognitiveVocabulary,
    downstream_need: OperatorInventionNeed,
    downstream_examples: Sequence[OperatorExample],
    *,
    intervention_arity: int = 2,
    probe_max_depth: int = 2,
    probe_max_candidates: int = 12000,
) -> InterventionDiscoveryReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    fields = schema.field_names
    canonical_fields = schema.canonical_fields
    if set(fields) != set(downstream_need.field_names):
        raise ValueError('ordered_field_names must match downstream need fields')
    probe_train = tuple(dict(row) for row in probe_training_contexts)
    probe_valid = tuple(dict(row) for row in probe_validation_contexts)
    if not probe_train:
        raise ValueError('probe_training_contexts must be non-empty')
    if not probe_valid:
        raise ValueError('probe_validation_contexts must be non-empty')
    if not downstream_examples:
        raise ValueError('downstream_examples must be non-empty')
    for row in (*probe_train, *probe_valid):
        schema.to_canonical_context(row)

    canonical_downstream_need = OperatorInventionNeed(
        downstream_need.objective,
        canonical_fields,
        downstream_need.output_field,
        constants=downstream_need.constants,
        max_depth=downstream_need.max_depth,
        max_candidates=downstream_need.max_candidates,
    )
    canonical_downstream_examples = tuple(
        OperatorExample(row.name, schema.to_canonical_context(row.context), row.expected)
        for row in downstream_examples
    )
    no_seed = synthesize_with_vocabulary(
        canonical_downstream_need,
        canonical_downstream_examples,
        vocabulary,
    )
    specs = enumerate_interventions(fields, anchor_values, arity=intervention_arity)
    receipts: list[InterventionCandidateReceipt] = []
    total_oracle_calls = 0

    for spec in specs:
        intervened_positions = {position for position, _value in spec.bindings}
        remaining_canonical_fields = tuple(
            field for index, field in enumerate(canonical_fields) if index not in intervened_positions
        )
        if not remaining_canonical_fields:
            receipts.append(InterventionCandidateReceipt(spec, False, 'no_free_probe_fields'))
            continue

        probe_examples: list[OperatorExample] = []
        outputs: list[object] = []
        invalid_oracle = False
        for index, context in enumerate(probe_train):
            applied = spec.apply(context, fields)
            try:
                expected = _oracle_value(oracle, applied)
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError):
                total_oracle_calls += 1
                invalid_oracle = True
                break
            total_oracle_calls += 1
            outputs.append(expected)
            probe_examples.append(OperatorExample(
                f'probe:{spec.intervention_id}:{index}',
                schema.to_canonical_context(applied),
                expected,
            ))

        if invalid_oracle:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'oracle_intervention_invalid',
                probe_oracle_calls=len(probe_examples) + 1,
            ))
            continue

        if len({_output_key(value) for value in outputs}) < 2:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'constant_probe_output',
                probe_oracle_calls=len(probe_examples),
            ))
            continue

        probe_need = OperatorInventionNeed(
            f'probe:{spec.intervention_id}',
            remaining_canonical_fields,
            'probe',
            constants=tuple(anchor_values),
            max_depth=int(probe_max_depth),
            max_candidates=int(probe_max_candidates),
        )
        base_probe = synthesize_base_with_budget(probe_need, tuple(probe_examples))
        vocab_probe = synthesize_with_vocabulary(probe_need, tuple(probe_examples), vocabulary)
        external_probe = (
            schema.externalize_expr(vocab_probe.expression)
            if vocab_probe.expression is not None else None
        )
        if base_probe.passed:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'base_probe_already_solved',
                base_probe_passed=True,
                vocabulary_probe_passed=bool(vocab_probe.passed),
                probe_expression=external_probe,
                probe_candidates_considered=vocab_probe.candidates_considered,
                probe_oracle_calls=len(probe_examples),
                used_abstraction_ids=vocab_probe.used_abstraction_ids,
            ))
            continue
        if not vocab_probe.passed or vocab_probe.expression is None:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'vocabulary_probe_unsolved',
                base_probe_passed=False,
                vocabulary_probe_passed=False,
                probe_candidates_considered=vocab_probe.candidates_considered,
                probe_oracle_calls=len(probe_examples),
            ))
            continue

        validation_exact = 0
        validation_calls = 0
        validation_invalid = False
        for context in probe_valid:
            applied = spec.apply(context, fields)
            try:
                expected = _oracle_value(oracle, applied)
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError):
                total_oracle_calls += 1
                validation_calls += 1
                validation_invalid = True
                break
            total_oracle_calls += 1
            validation_calls += 1
            try:
                actual = evaluate_with_vocabulary(
                    vocab_probe.expression,
                    schema.to_canonical_context(applied),
                    vocabulary,
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                actual = object()
            validation_exact += int(_equivalent(actual, expected))
        if validation_invalid:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'probe_validation_oracle_invalid',
                base_probe_passed=False,
                vocabulary_probe_passed=True,
                probe_expression=external_probe,
                probe_candidates_considered=vocab_probe.candidates_considered,
                probe_validation_cases=len(probe_valid),
                probe_validation_exact=validation_exact,
                probe_oracle_calls=len(probe_examples),
                validation_oracle_calls=validation_calls,
                used_abstraction_ids=vocab_probe.used_abstraction_ids,
            ))
            continue
        if validation_exact != len(probe_valid):
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'probe_validation_failed',
                base_probe_passed=False,
                vocabulary_probe_passed=True,
                probe_expression=external_probe,
                probe_candidates_considered=vocab_probe.candidates_considered,
                probe_validation_cases=len(probe_valid),
                probe_validation_exact=validation_exact,
                probe_oracle_calls=len(probe_examples),
                validation_oracle_calls=validation_calls,
                used_abstraction_ids=vocab_probe.used_abstraction_ids,
            ))
            continue

        if no_seed.passed:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'downstream_baseline_already_passed',
                base_probe_passed=False,
                vocabulary_probe_passed=True,
                probe_expression=external_probe,
                probe_candidates_considered=vocab_probe.candidates_considered,
                probe_validation_cases=len(probe_valid),
                probe_validation_exact=validation_exact,
                probe_oracle_calls=len(probe_examples),
                validation_oracle_calls=validation_calls,
                used_abstraction_ids=vocab_probe.used_abstraction_ids,
            ))
            continue

        seeded = synthesize_with_vocabulary(
            canonical_downstream_need,
            canonical_downstream_examples,
            vocabulary,
            seed_expressions=(vocab_probe.expression,),
        )
        external_seeded = (
            schema.externalize_expr(seeded.expression)
            if seeded.expression is not None else None
        )
        if not seeded.passed:
            receipts.append(InterventionCandidateReceipt(
                spec, False, 'no_causal_downstream_gain',
                base_probe_passed=False,
                vocabulary_probe_passed=True,
                probe_expression=external_probe,
                probe_candidates_considered=vocab_probe.candidates_considered,
                probe_validation_cases=len(probe_valid),
                probe_validation_exact=validation_exact,
                probe_oracle_calls=len(probe_examples),
                validation_oracle_calls=validation_calls,
                seeded_downstream_passed=False,
                seeded_downstream_candidates_considered=seeded.candidates_considered,
                used_abstraction_ids=vocab_probe.used_abstraction_ids,
                seeded_downstream_expression=external_seeded,
            ))
            continue

        receipts.append(InterventionCandidateReceipt(
            spec, True, 'causal_probe_verified',
            base_probe_passed=False,
            vocabulary_probe_passed=True,
            probe_expression=external_probe,
            probe_candidates_considered=vocab_probe.candidates_considered,
            probe_validation_cases=len(probe_valid),
            probe_validation_exact=validation_exact,
            probe_oracle_calls=len(probe_examples),
            validation_oracle_calls=validation_calls,
            seeded_downstream_passed=True,
            seeded_downstream_candidates_considered=seeded.candidates_considered,
            used_abstraction_ids=vocab_probe.used_abstraction_ids,
            seeded_downstream_expression=external_seeded,
        ))

    passing = [row for row in receipts if row.passed]
    selected = min(
        passing,
        key=lambda row: (
            row.seeded_downstream_candidates_considered,
            row.probe_candidates_considered,
            row.validation_oracle_calls,
            row.intervention.intervention_id,
        ),
        default=None,
    )
    return InterventionDiscoveryReceipt(
        passed=selected is not None,
        selected=selected,
        candidates=tuple(receipts),
        no_seed_passed=bool(no_seed.passed),
        no_seed_candidates_considered=no_seed.candidates_considered,
        oracle_calls=total_oracle_calls,
        reason='causal_intervention_discovered' if selected is not None else 'no_causal_intervention_within_budget',
        trainable_parameter_count=0,
    )


__all__ = [
    'PositionalSchema', 'InterventionSpec', 'InterventionCandidateReceipt', 'InterventionDiscoveryReceipt',
    'enumerate_interventions', 'discover_causal_intervention',
]
