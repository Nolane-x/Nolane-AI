from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Expr, evaluate_expr
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary_synthesis import synthesize_base_with_budget
from .r258_intervention_discovery import InterventionSpec, PositionalSchema, enumerate_interventions
from .r259_semantic_index_core import derive_anchor_values, semantic_vector_key

_NUMERIC_COMPOSITION_OPS = ('add', 'sub', 'rsub', 'mul', 'min', 'max')
_COMMUTATIVE_OPS = frozenset({'add', 'mul', 'min', 'max'})


def _numeric(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('R2.61 composition values must be numeric scalars')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('R2.61 composition values must be finite')
    return value


def _equivalent(actual: object, expected: object) -> bool:
    if (
        isinstance(actual, (int, float)) and not isinstance(actual, bool)
        and isinstance(expected, (int, float)) and not isinstance(expected, bool)
    ):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False
    return actual == expected


def _oracle_value(oracle: Callable[[Mapping[str, object]], object], context: Mapping[str, object]) -> object:
    value = oracle(dict(context))
    semantic_vector_key((value,))
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('oracle output must be finite')
    return value


def _compose_value(op: str, left: object, right: object) -> float:
    a = _numeric(left)
    b = _numeric(right)
    if op == 'add':
        out = a + b
    elif op == 'sub':
        out = a - b
    elif op == 'rsub':
        out = b - a
    elif op == 'mul':
        out = a * b
    elif op == 'min':
        out = min(a, b)
    elif op == 'max':
        out = max(a, b)
    else:
        raise ValueError(f'unsupported composition op: {op}')
    if not math.isfinite(out):
        raise ValueError('composition output must be finite')
    return out


def _compose_expr(op: str, left: Expr, right: Expr) -> Expr:
    if op == 'rsub':
        return Binary('sub', right, left)
    if op not in {'add', 'sub', 'mul', 'min', 'max'}:
        raise ValueError(f'unsupported composition op: {op}')
    return Binary(op, left, right)


def _program_id(op: str, interventions: tuple[InterventionSpec, InterventionSpec]) -> str:
    rows = interventions
    if op in _COMMUTATIVE_OPS:
        rows = tuple(sorted(rows, key=lambda spec: spec.intervention_id))
    payload = {
        'composition_op': op,
        'interventions': [
            [[int(position), float(value)] for position, value in spec.bindings]
            for spec in rows
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return f'exp2.{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'


@dataclass(frozen=True, slots=True)
class InterventionProfile:
    intervention: InterventionSpec
    discovery_outputs: tuple[object, ...]
    validation_outputs: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class ComplementaryExperimentProgram:
    interventions: tuple[InterventionSpec, InterventionSpec]
    composition_op: str
    program_id: str


@dataclass(frozen=True, slots=True)
class ComplementaryProgramCandidate:
    program: ComplementaryExperimentProgram
    left_profile: InterventionProfile
    right_profile: InterventionProfile
    left_alone_exact: bool
    right_alone_exact: bool
    left_essential_cases: int
    right_essential_cases: int
    discovery_exact: int
    validation_exact: int
    proper_subset_failures: int


@dataclass(frozen=True, slots=True)
class ComplementaryStructureReceipt:
    passed: bool
    selected: ComplementaryProgramCandidate | None
    passing_programs: int
    legal_interventions: int
    invalid_interventions_rejected: int
    degenerate_interventions_rejected: int
    intervention_candidates_considered: int
    pair_operation_candidates_considered: int
    discovery_target_outputs: tuple[object, ...]
    validation_target_outputs: tuple[object, ...]
    oracle_calls: int
    reason: str
    trainable_parameter_count: int = 0


@dataclass(frozen=True, slots=True)
class ComplementarySynthesisReceipt:
    passed: bool
    structure: ComplementaryStructureReceipt
    expression: Expr | None
    probe_expressions: tuple[Expr, ...]
    baseline_passed: bool
    baseline_candidates_considered: int
    probe_candidates_considered: tuple[int, ...]
    matched_synthesis_budget_respected: bool
    validation_cases: int
    validation_exact: int
    singleton_validation_exact: tuple[int, ...]
    reason: str
    trainable_parameter_count: int = 0


def discover_complementary_experiment_structure(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_ops: Sequence[str] = _NUMERIC_COMPOSITION_OPS,
    min_essential_cases: int = 1,
) -> ComplementaryStructureReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    if context_validator is not None and not callable(context_validator):
        raise TypeError('context_validator must be callable or None')
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    if not discovery or not validation:
        raise ValueError('discovery and validation contexts must be non-empty')
    for row in (*discovery, *validation):
        schema.to_canonical_context(row)
        if context_validator is not None and not bool(context_validator(row)):
            raise ValueError('original contexts must satisfy context_validator')
    ops = tuple(dict.fromkeys(map(str, composition_ops)))
    if not ops or any(op not in _NUMERIC_COMPOSITION_OPS for op in ops):
        raise ValueError('composition_ops must be supported finite numeric operations')
    min_essential_cases = int(min_essential_cases)
    if min_essential_cases < 1:
        raise ValueError('min_essential_cases must be positive')

    oracle_calls = 0
    discovery_targets: list[object] = []
    validation_targets: list[object] = []
    for context in discovery:
        discovery_targets.append(_oracle_value(oracle, context))
        oracle_calls += 1
    for context in validation:
        validation_targets.append(_oracle_value(oracle, context))
        oracle_calls += 1

    specs = enumerate_interventions(schema.field_names, anchor_values, arity=int(intervention_arity))
    profiles: list[InterventionProfile] = []
    invalid_rejected = 0
    degenerate_rejected = 0

    for spec in specs:
        applied_discovery = tuple(spec.apply(row, schema.field_names) for row in discovery)
        applied_validation = tuple(spec.apply(row, schema.field_names) for row in validation)
        if context_validator is not None and any(
            not bool(context_validator(row)) for row in (*applied_discovery, *applied_validation)
        ):
            invalid_rejected += 1
            continue
        d_outputs: list[object] = []
        v_outputs: list[object] = []
        invalid = False
        for context in applied_discovery:
            try:
                d_outputs.append(_oracle_value(oracle, context))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            invalid_rejected += 1
            continue
        for context in applied_validation:
            try:
                v_outputs.append(_oracle_value(oracle, context))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            invalid_rejected += 1
            continue
        if len({semantic_vector_key((value,)) for value in d_outputs}) < 2:
            degenerate_rejected += 1
            continue
        if all(_equivalent(a, b) for a, b in zip(d_outputs, discovery_targets, strict=True)) and all(
            _equivalent(a, b) for a, b in zip(v_outputs, validation_targets, strict=True)
        ):
            # A singleton that already solves the target is not complementary evidence.
            degenerate_rejected += 1
            continue
        profiles.append(InterventionProfile(spec, tuple(d_outputs), tuple(v_outputs)))

    profiles.sort(key=lambda row: row.intervention.intervention_id)
    passing: list[ComplementaryProgramCandidate] = []
    pair_ops_considered = 0
    all_targets = tuple(discovery_targets) + tuple(validation_targets)

    for left, right in itertools.combinations(profiles, 2):
        left_all = left.discovery_outputs + left.validation_outputs
        right_all = right.discovery_outputs + right.validation_outputs
        for op in ops:
            pair_ops_considered += 1
            try:
                d_composed = tuple(
                    _compose_value(op, a, b)
                    for a, b in zip(left.discovery_outputs, right.discovery_outputs, strict=True)
                )
                v_composed = tuple(
                    _compose_value(op, a, b)
                    for a, b in zip(left.validation_outputs, right.validation_outputs, strict=True)
                )
            except (TypeError, ValueError, OverflowError, ZeroDivisionError):
                continue
            d_exact = sum(_equivalent(a, b) for a, b in zip(d_composed, discovery_targets, strict=True))
            if d_exact != len(discovery_targets):
                continue
            v_exact = sum(_equivalent(a, b) for a, b in zip(v_composed, validation_targets, strict=True))
            if v_exact != len(validation_targets):
                continue
            left_exact = all(_equivalent(a, b) for a, b in zip(left_all, all_targets, strict=True))
            right_exact = all(_equivalent(a, b) for a, b in zip(right_all, all_targets, strict=True))
            if left_exact or right_exact:
                continue
            composed_all = d_composed + v_composed
            left_essential = sum(
                not _equivalent(full, right_value)
                for full, right_value in zip(composed_all, right_all, strict=True)
            )
            right_essential = sum(
                not _equivalent(full, left_value)
                for full, left_value in zip(composed_all, left_all, strict=True)
            )
            if left_essential < min_essential_cases or right_essential < min_essential_cases:
                continue
            candidate_left = left
            candidate_right = right
            interventions = (candidate_left.intervention, candidate_right.intervention)
            if op in _COMMUTATIVE_OPS:
                interventions = tuple(sorted(interventions, key=lambda spec: spec.intervention_id))  # type: ignore[assignment]
                if interventions[0] != candidate_left.intervention:
                    candidate_left, candidate_right = candidate_right, candidate_left
            program = ComplementaryExperimentProgram(
                interventions=interventions,
                composition_op=op,
                program_id=_program_id(op, interventions),
            )
            passing.append(ComplementaryProgramCandidate(
                program=program,
                left_profile=candidate_left,
                right_profile=candidate_right,
                left_alone_exact=False,
                right_alone_exact=False,
                left_essential_cases=left_essential,
                right_essential_cases=right_essential,
                discovery_exact=d_exact,
                validation_exact=v_exact,
                proper_subset_failures=2,
            ))

    passing.sort(key=lambda row: (
        row.program.interventions[0].intervention_id,
        row.program.interventions[1].intervention_id,
        ops.index(row.program.composition_op),
        row.program.program_id,
    ))
    selected = passing[0] if passing else None
    return ComplementaryStructureReceipt(
        passed=selected is not None,
        selected=selected,
        passing_programs=len(passing),
        legal_interventions=len(profiles),
        invalid_interventions_rejected=invalid_rejected,
        degenerate_interventions_rejected=degenerate_rejected,
        intervention_candidates_considered=len(specs),
        pair_operation_candidates_considered=pair_ops_considered,
        discovery_target_outputs=tuple(discovery_targets),
        validation_target_outputs=tuple(validation_targets),
        oracle_calls=oracle_calls,
        reason='complementary_program_discovered' if selected is not None else 'no_complementary_program',
        trainable_parameter_count=0,
    )


def _project_context(
    schema: PositionalSchema,
    context: Mapping[str, object],
    free_positions: tuple[int, ...],
) -> dict[str, object]:
    canonical = schema.to_canonical_context(context)
    return {schema.canonical_fields[position]: canonical[schema.canonical_fields[position]] for position in free_positions}


def synthesize_complementary_experiment_program(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    program_need: OperatorInventionNeed,
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_ops: Sequence[str] = _NUMERIC_COMPOSITION_OPS,
    probe_constants: Sequence[object] = (0.0,),
    probe_max_depth: int = 2,
    probe_max_candidates: int = 5000,
) -> ComplementarySynthesisReceipt:
    if not isinstance(program_need, OperatorInventionNeed):
        raise TypeError('program_need must be OperatorInventionNeed')
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    if set(schema.field_names) != set(program_need.field_names):
        raise ValueError('ordered_field_names must match program_need fields')
    anchors = derive_anchor_values(program_need, min_count=int(intervention_arity))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    structure = discover_complementary_experiment_structure(
        oracle,
        schema.field_names,
        anchors,
        discovery,
        validation,
        context_validator=context_validator,
        intervention_arity=intervention_arity,
        composition_ops=composition_ops,
    )
    if not structure.passed or structure.selected is None:
        return ComplementarySynthesisReceipt(
            False, structure, None, (), False, 0, (), False,
            len(validation), 0, (), 'structure_discovery_failed', 0,
        )

    canonical_target_examples = tuple(
        OperatorExample(
            f'target:{index}',
            schema.to_canonical_context(context),
            expected,
        )
        for index, (context, expected) in enumerate(zip(discovery, structure.discovery_target_outputs, strict=True))
    )
    baseline_need = OperatorInventionNeed(
        f'{program_need.objective}:flat-baseline',
        schema.canonical_fields,
        program_need.output_field,
        constants=tuple(probe_constants),
        max_depth=int(probe_max_depth),
        max_candidates=int(program_need.max_candidates),
    )
    baseline = synthesize_base_with_budget(baseline_need, canonical_target_examples)
    if baseline.passed:
        return ComplementarySynthesisReceipt(
            False, structure, schema.externalize_expr(baseline.expression) if baseline.expression else None, (),
            True, baseline.candidates_considered, (), False,
            len(validation), 0, (), 'flat_baseline_already_passed', 0,
        )

    selected = structure.selected
    profile_by_id = {
        selected.left_profile.intervention.intervention_id: selected.left_profile,
        selected.right_profile.intervention.intervention_id: selected.right_profile,
    }
    canonical_probes: list[Expr] = []
    external_probes: list[Expr] = []
    probe_counts: list[int] = []
    singleton_validation_exact: list[int] = []

    for spec in selected.program.interventions:
        profile = profile_by_id[spec.intervention_id]
        fixed = {position for position, _value in spec.bindings}
        free_positions = tuple(position for position in range(len(schema.field_names)) if position not in fixed)
        probe_examples = tuple(
            OperatorExample(
                f'probe:{spec.intervention_id}:{index}',
                _project_context(schema, spec.apply(context, schema.field_names), free_positions),
                expected,
            )
            for index, (context, expected) in enumerate(zip(discovery, profile.discovery_outputs, strict=True))
        )
        probe_need = OperatorInventionNeed(
            f'probe:{spec.intervention_id}',
            tuple(schema.canonical_fields[position] for position in free_positions),
            'probe_out',
            constants=tuple(probe_constants),
            max_depth=int(probe_max_depth),
            max_candidates=int(probe_max_candidates),
        )
        synthesized = synthesize_base_with_budget(probe_need, probe_examples)
        probe_counts.append(synthesized.candidates_considered)
        if not synthesized.passed or synthesized.expression is None:
            return ComplementarySynthesisReceipt(
                False, structure, None, tuple(external_probes), False,
                baseline.candidates_considered, tuple(probe_counts),
                sum(probe_counts) <= baseline.candidates_considered,
                len(validation), 0, tuple(singleton_validation_exact),
                'selected_probe_unsolved', 0,
            )
        validation_exact = 0
        singleton_exact = 0
        for context, expected_probe, expected_target in zip(
            validation,
            profile.validation_outputs,
            structure.validation_target_outputs,
            strict=True,
        ):
            applied = spec.apply(context, schema.field_names)
            try:
                probe_actual = evaluate_expr(synthesized.expression, _project_context(schema, applied, free_positions))
                singleton_actual = evaluate_expr(synthesized.expression, schema.to_canonical_context(context))
            except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                probe_actual = object()
                singleton_actual = object()
            validation_exact += int(_equivalent(probe_actual, expected_probe))
            singleton_exact += int(_equivalent(singleton_actual, expected_target))
        if validation_exact != len(validation):
            return ComplementarySynthesisReceipt(
                False, structure, None, tuple(external_probes), False,
                baseline.candidates_considered, tuple(probe_counts),
                sum(probe_counts) <= baseline.candidates_considered,
                len(validation), 0, tuple(singleton_validation_exact + [singleton_exact]),
                'selected_probe_validation_failed', 0,
            )
        canonical_probes.append(synthesized.expression)
        external_probes.append(schema.externalize_expr(synthesized.expression))
        singleton_validation_exact.append(singleton_exact)

    budget_respected = sum(probe_counts) <= baseline.candidates_considered
    if not budget_respected:
        return ComplementarySynthesisReceipt(
            False, structure, None, tuple(external_probes), False,
            baseline.candidates_considered, tuple(probe_counts), False,
            len(validation), 0, tuple(singleton_validation_exact),
            'matched_synthesis_budget_exceeded', 0,
        )

    combined = _compose_expr(selected.program.composition_op, canonical_probes[0], canonical_probes[1])
    full_exact = 0
    for context, expected in zip(validation, structure.validation_target_outputs, strict=True):
        try:
            actual = evaluate_expr(combined, schema.to_canonical_context(context))
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            actual = object()
        full_exact += int(_equivalent(actual, expected))
    if full_exact != len(validation) or any(exact == len(validation) for exact in singleton_validation_exact):
        return ComplementarySynthesisReceipt(
            False, structure, schema.externalize_expr(combined), tuple(external_probes), False,
            baseline.candidates_considered, tuple(probe_counts), True,
            len(validation), full_exact, tuple(singleton_validation_exact),
            'full_program_or_subset_validation_failed', 0,
        )

    return ComplementarySynthesisReceipt(
        True,
        structure,
        schema.externalize_expr(combined),
        tuple(external_probes),
        False,
        baseline.candidates_considered,
        tuple(probe_counts),
        True,
        len(validation),
        full_exact,
        tuple(singleton_validation_exact),
        'complementary_hierarchical_synthesis_verified',
        0,
    )


__all__ = [
    'InterventionProfile', 'ComplementaryExperimentProgram', 'ComplementaryProgramCandidate',
    'ComplementaryStructureReceipt', 'ComplementarySynthesisReceipt',
    'discover_complementary_experiment_structure', 'synthesize_complementary_experiment_program',
]
