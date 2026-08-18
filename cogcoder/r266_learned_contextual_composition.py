from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, evaluate_expr, expr_digest
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r258_intervention_discovery import InterventionSpec, PositionalSchema, enumerate_interventions
from .r259_semantic_index_core import derive_anchor_values, semantic_vector_key

_R262_FIXED_OPS = ('add', 'sub', 'rsub', 'mul', 'min', 'max')
_UNARY_LEAF_OPS = ('abs', 'neg', 'not')
_BINARY_LEAF_OPS = ('add', 'sub', 'mul', 'div', 'min', 'max', 'eq', 'ne', 'lt', 'le', 'gt', 'ge', 'and', 'or')


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


def _finite_json_value(value: object) -> object:
    try:
        json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError('values must be finite JSON-compatible scalars') from exc
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('numeric values must be finite')
    return value


def _oracle_value(oracle: Callable[[Mapping[str, object]], object], context: Mapping[str, object]) -> object:
    return _finite_json_value(oracle(dict(context)))


def _used_fields(expr: Expr) -> tuple[str, ...]:
    out: set[str] = set()

    def walk(node: Expr) -> None:
        if isinstance(node, Field):
            out.add(node.name)
            return
        if isinstance(node, Unary):
            walk(node.arg)
            return
        if isinstance(node, Binary):
            walk(node.left)
            walk(node.right)
            return
        if isinstance(node, IfElse):
            walk(node.condition)
            walk(node.when_true)
            walk(node.when_false)
            return
        if isinstance(node, Const):
            return
        raise TypeError(f'unsupported expression node: {type(node).__name__}')

    walk(expr)
    return tuple(sorted(out))


def _fixed_compose(op: str, left: object, right: object) -> object:
    if (
        isinstance(left, bool) or isinstance(right, bool)
        or not isinstance(left, (int, float)) or not isinstance(right, (int, float))
    ):
        raise TypeError('R2.62 fixed composition requires numeric scalar values')
    a = float(left)
    b = float(right)
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError('R2.62 fixed composition requires finite values')
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
        raise ValueError(f'unknown fixed op: {op}')
    if not math.isfinite(out):
        raise ValueError('fixed composition produced a non-finite value')
    return out


@dataclass(frozen=True, slots=True)
class ContextualExpressionReceipt:
    passed: bool
    expression: Expr | None
    candidates_considered: int
    search_evaluations: int
    semantic_candidates: int
    reason: str


@dataclass(frozen=True, slots=True)
class _SemanticCandidate:
    expression: Expr
    values: tuple[object, ...]

    @property
    def rank(self) -> tuple[int, int, str]:
        return (self.expression.depth, self.expression.cost, expr_digest(self.expression))

    @property
    def boolean(self) -> bool:
        return bool(self.values) and all(isinstance(value, bool) for value in self.values)


def synthesize_contextual_expression(
    field_names: Sequence[str],
    constants: Sequence[object],
    examples: Sequence[OperatorExample],
    *,
    max_depth: int = 2,
    max_candidates: int = 12000,
) -> ContextualExpressionReceipt:
    """Synthesize a bounded contextual expression with decision-tree priority.

    The semantic base contains atomic fields/constants and one-step trusted DSL
    transforms.  Conditionals are then built recursively from boolean semantic
    predicates and these leaves.  This makes depth-2/3 contextual routers reachable
    without enumerating the generic DSL's full Cartesian conditional space.
    """

    fields = tuple(str(value).strip() for value in field_names)
    if not fields or any(not value for value in fields) or len(set(fields)) != len(fields):
        raise ValueError('field_names must be distinct non-empty strings')
    rows = tuple(examples)
    if not rows or not all(isinstance(row, OperatorExample) for row in rows):
        raise ValueError('examples must contain OperatorExample values')
    max_depth = int(max_depth)
    max_candidates = int(max_candidates)
    if max_depth < 0:
        raise ValueError('max_depth must be non-negative')
    if max_candidates < 1:
        raise ValueError('max_candidates must be positive')
    target = tuple(_finite_json_value(row.expected) for row in rows)

    considered = 0
    evaluations = 0
    semantic_seen: set[str] = set()
    digest_seen: set[str] = set()
    pool: list[_SemanticCandidate] = []

    def eval_expr(expr: Expr) -> tuple[object, ...] | None:
        nonlocal evaluations
        values: list[object] = []
        for row in rows:
            try:
                value = _finite_json_value(evaluate_expr(expr, row.context))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                evaluations += 1
                return None
            evaluations += 1
            values.append(value)
        return tuple(values)

    def add(expr: Expr) -> ContextualExpressionReceipt | None:
        nonlocal considered
        if considered >= max_candidates:
            return ContextualExpressionReceipt(
                False, None, considered, evaluations, len(pool), 'contextual_budget_exhausted',
            )
        digest = expr_digest(expr)
        if digest in digest_seen:
            return None
        digest_seen.add(digest)
        considered += 1
        values = eval_expr(expr)
        if values is None:
            return None
        key = semantic_vector_key(values)
        if key in semantic_seen:
            return None
        semantic_seen.add(key)
        candidate = _SemanticCandidate(expr, values)
        pool.append(candidate)
        if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
            return ContextualExpressionReceipt(True, expr, considered, evaluations, len(pool), 'contextual_exact')
        return None

    atoms: list[Expr] = [Field(name) for name in sorted(fields)]
    constant_keys: set[str] = set()
    for raw in constants:
        try:
            value = _finite_json_value(raw)
            key = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if key not in constant_keys:
                constant_keys.add(key)
                atoms.append(Const(value))
        except (TypeError, ValueError):
            continue

    for expr in atoms:
        hit = add(expr)
        if hit is not None:
            return hit
        if considered >= max_candidates:
            return ContextualExpressionReceipt(False, None, considered, evaluations, len(pool), 'contextual_budget_exhausted')

    if max_depth >= 1:
        for arg in atoms:
            for op in _UNARY_LEAF_OPS:
                hit = add(Unary(op, arg))
                if hit is not None:
                    return hit
                if considered >= max_candidates:
                    return ContextualExpressionReceipt(False, None, considered, evaluations, len(pool), 'contextual_budget_exhausted')
        for left in atoms:
            for right in atoms:
                for op in _BINARY_LEAF_OPS:
                    try:
                        expr = Binary(op, left, right)
                    except (TypeError, ValueError):
                        continue
                    hit = add(expr)
                    if hit is not None:
                        return hit
                    if considered >= max_candidates:
                        return ContextualExpressionReceipt(False, None, considered, evaluations, len(pool), 'contextual_budget_exhausted')

    # Use only semantically useful one-step candidates as decision leaves and predicates.
    # Recursive subset solving can synthesize nested conditional programs while each
    # constructed IfElse is still charged to the same hard candidate ledger.
    leaf_pool = tuple(sorted(pool, key=lambda row: row.rank))
    condition_pool = tuple(row for row in leaf_pool if row.boolean)
    memo: dict[tuple[tuple[int, ...], int], Expr | None] = {}
    constructed: dict[str, _SemanticCandidate] = {}
    budget_exhausted = False

    def matches(candidate: _SemanticCandidate, indices: tuple[int, ...]) -> bool:
        return all(_equivalent(candidate.values[index], target[index]) for index in indices)

    def solve(indices: tuple[int, ...], depth_limit: int) -> Expr | None:
        nonlocal considered, evaluations, budget_exhausted
        key = (indices, depth_limit)
        if key in memo:
            return memo[key]
        for candidate in leaf_pool:
            if candidate.expression.depth <= depth_limit and matches(candidate, indices):
                memo[key] = candidate.expression
                return candidate.expression
        if depth_limit <= 0:
            memo[key] = None
            return None

        for condition in condition_pool:
            if condition.expression.depth >= depth_limit:
                continue
            true_indices = tuple(index for index in indices if condition.values[index] is True)
            false_indices = tuple(index for index in indices if condition.values[index] is False)
            if not true_indices or not false_indices:
                continue
            branch_limit = depth_limit - 1
            when_true = solve(true_indices, branch_limit)
            if when_true is None:
                if budget_exhausted:
                    memo[key] = None
                    return None
                continue
            when_false = solve(false_indices, branch_limit)
            if when_false is None:
                if budget_exhausted:
                    memo[key] = None
                    return None
                continue
            expr = IfElse(condition.expression, when_true, when_false)
            if expr.depth > depth_limit:
                continue
            digest = expr_digest(expr)
            if digest in constructed:
                candidate = constructed[digest]
            else:
                if considered >= max_candidates:
                    budget_exhausted = True
                    memo[key] = None
                    return None
                considered += 1
                values: list[object] = []
                valid = True
                for row in rows:
                    try:
                        value = _finite_json_value(evaluate_expr(expr, row.context))
                    except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                        evaluations += 1
                        valid = False
                        break
                    evaluations += 1
                    values.append(value)
                if not valid:
                    continue
                candidate = _SemanticCandidate(expr, tuple(values))
                constructed[digest] = candidate
            if matches(candidate, indices):
                memo[key] = expr
                return expr

        memo[key] = None
        return None

    full_indices = tuple(range(len(rows)))
    expression = solve(full_indices, max_depth)
    if expression is not None:
        return ContextualExpressionReceipt(
            True, expression, considered, evaluations, len(pool) + len(constructed), 'contextual_exact',
        )
    return ContextualExpressionReceipt(
        False,
        None,
        considered,
        evaluations,
        len(pool) + len(constructed),
        'contextual_budget_exhausted' if budget_exhausted else 'no_contextual_expression',
    )


@dataclass(frozen=True, slots=True)
class ContextualInterventionProfile:
    intervention: InterventionSpec
    discovery_outputs: tuple[object, ...]
    validation_outputs: tuple[object, ...]

    @property
    def outputs(self) -> tuple[object, ...]:
        return self.discovery_outputs + self.validation_outputs


@dataclass(frozen=True, slots=True)
class ContextualCompositionProgram:
    interventions: tuple[InterventionSpec, InterventionSpec]
    shared_positions: tuple[int, ...]
    composition_expression: Expr
    composition_digest: str
    program_id: str


@dataclass(frozen=True, slots=True)
class ContextualCompositionCandidate:
    program: ContextualCompositionProgram
    left_profile: ContextualInterventionProfile
    right_profile: ContextualInterventionProfile
    used_composition_fields: tuple[str, ...]
    selection_cases: int
    selection_exact: int
    r262_fixed_op_passed: bool
    r262_fixed_op_exact: tuple[tuple[str, int], ...]
    singleton_composition_passed: tuple[bool, bool]
    singleton_candidates_considered: tuple[int, int]
    composition_candidates_considered: int


@dataclass(frozen=True, slots=True)
class ContextualCompositionStructureReceipt:
    passed: bool
    selected: ContextualCompositionCandidate | None
    passing_programs: int
    legal_interventions: int
    invalid_interventions_rejected: int
    degenerate_interventions_rejected: int
    intervention_candidates_considered: int
    composition_candidates_considered: int
    singleton_candidates_considered: int
    oracle_calls: int
    false_accepts: int
    reason: str
    trainable_parameter_count: int = 0


def _profile_semantic_id(profile: ContextualInterventionProfile) -> str:
    raw = json.dumps(list(profile.outputs), sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _program_id(
    interventions: tuple[InterventionSpec, InterventionSpec],
    shared_positions: tuple[int, ...],
    expression: Expr,
) -> str:
    payload = {
        'interventions': [
            [[int(position), float(value)] for position, value in spec.bindings]
            for spec in interventions
        ],
        'shared_positions': [int(value) for value in shared_positions],
        'composition': expression.to_data(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return f'ctx2.{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'


def _composition_examples(
    schema: PositionalSchema,
    contexts: Sequence[Mapping[str, object]],
    targets: Sequence[object],
    left_outputs: Sequence[object],
    right_outputs: Sequence[object] | None,
    shared_positions: tuple[int, ...],
) -> tuple[OperatorExample, ...]:
    out: list[OperatorExample] = []
    for index, (context, expected, left) in enumerate(zip(contexts, targets, left_outputs, strict=True)):
        canonical = schema.to_canonical_context(context)
        row: dict[str, object] = {'__p0': left}
        if right_outputs is not None:
            row['__p1'] = right_outputs[index]
        for position in shared_positions:
            field = schema.canonical_fields[position]
            row[field] = canonical[field]
        out.append(OperatorExample(f'ctx:{index}', row, expected))
    return tuple(out)


def discover_contextual_composition_structure(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_constants: Sequence[object] = (0.0,),
    composition_max_depth: int = 2,
    composition_max_candidates_per_pair: int = 12000,
    max_composition_candidates_total: int = 120000,
) -> ContextualCompositionStructureReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    if context_validator is not None and not callable(context_validator):
        raise TypeError('context_validator must be callable or None')
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    if not discovery or not validation:
        raise ValueError('discovery_contexts and validation_contexts must be non-empty')
    for row in (*discovery, *validation):
        schema.to_canonical_context(row)
        if context_validator is not None and not bool(context_validator(row)):
            raise ValueError('original contexts must satisfy context_validator')

    max_total = int(max_composition_candidates_total)
    if max_total < 1:
        raise ValueError('max_composition_candidates_total must be positive')
    per_pair = int(composition_max_candidates_per_pair)
    if per_pair < 1:
        raise ValueError('composition_max_candidates_per_pair must be positive')

    oracle_calls = 0
    discovery_target_rows: list[object] = []
    validation_target_rows: list[object] = []
    try:
        for row in discovery:
            oracle_calls += 1
            discovery_target_rows.append(_oracle_value(oracle, row))
        for row in validation:
            oracle_calls += 1
            validation_target_rows.append(_oracle_value(oracle, row))
    except Exception as exc:
        return ContextualCompositionStructureReceipt(
            False, None, 0, 0, 0, 0, 0, 0, 0, oracle_calls, 0,
            f'oracle_error:{type(exc).__name__}:{exc}', 0,
        )
    discovery_targets = tuple(discovery_target_rows)
    validation_targets = tuple(validation_target_rows)

    specs = enumerate_interventions(schema.field_names, tuple(map(float, anchor_values)), arity=int(intervention_arity))
    profiles: list[ContextualInterventionProfile] = []
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
        d_values: list[object] = []
        v_values: list[object] = []
        invalid = False
        for row in applied_discovery:
            try:
                d_values.append(_oracle_value(oracle, row))
            except Exception:
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            invalid_rejected += 1
            continue
        for row in applied_validation:
            try:
                v_values.append(_oracle_value(oracle, row))
            except Exception:
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            invalid_rejected += 1
            continue
        all_values = tuple(d_values) + tuple(v_values)
        if len({semantic_vector_key((value,)) for value in all_values}) < 2:
            degenerate_rejected += 1
            continue
        all_targets = discovery_targets + validation_targets
        if all(_equivalent(actual, expected) for actual, expected in zip(all_values, all_targets, strict=True)):
            degenerate_rejected += 1
            continue
        profiles.append(ContextualInterventionProfile(spec, tuple(d_values), tuple(v_values)))

    profiles.sort(key=lambda row: row.intervention.intervention_id)
    selection_contexts = discovery + validation
    selection_targets = discovery_targets + validation_targets
    passing: list[ContextualCompositionCandidate] = []
    total_composition_candidates = 0
    total_singleton_candidates = 0
    exhausted = False

    for left, right in itertools.combinations(profiles, 2):
        fixed_positions = {position for position, _value in left.intervention.bindings}
        fixed_positions.update(position for position, _value in right.intervention.bindings)
        shared_positions = tuple(index for index in range(len(schema.field_names)) if index not in fixed_positions)
        fields = ('__p0', '__p1') + tuple(schema.canonical_fields[index] for index in shared_positions)
        remaining = max_total - total_composition_candidates
        if remaining <= 0:
            exhausted = True
            break
        pair_budget = min(per_pair, remaining)
        examples = _composition_examples(
            schema,
            selection_contexts,
            selection_targets,
            left.outputs,
            right.outputs,
            shared_positions,
        )
        composition = synthesize_contextual_expression(
            fields,
            tuple(composition_constants),
            examples,
            max_depth=int(composition_max_depth),
            max_candidates=pair_budget,
        )
        total_composition_candidates += composition.candidates_considered
        if not composition.passed or composition.expression is None:
            if composition.reason == 'contextual_budget_exhausted' and total_composition_candidates >= max_total:
                exhausted = True
                break
            continue
        used = _used_fields(composition.expression)
        if not {'__p0', '__p1'} <= set(used):
            continue

        fixed_rows: list[tuple[str, int]] = []
        fixed_pass = False
        for op in _R262_FIXED_OPS:
            exact = 0
            for lvalue, rvalue, expected in zip(left.outputs, right.outputs, selection_targets, strict=True):
                try:
                    actual = _fixed_compose(op, lvalue, rvalue)
                except (TypeError, ValueError, OverflowError, ZeroDivisionError):
                    actual = object()
                exact += int(_equivalent(actual, expected))
            fixed_rows.append((op, exact))
            if exact == len(selection_targets):
                fixed_pass = True
        if fixed_pass:
            continue

        singleton_passed: list[bool] = []
        singleton_counts: list[int] = []
        for probe_name, outputs in (('__p0', left.outputs), ('__p0', right.outputs)):
            single_fields = (probe_name,) + tuple(schema.canonical_fields[index] for index in shared_positions)
            single_examples = _composition_examples(
                schema,
                selection_contexts,
                selection_targets,
                outputs,
                None,
                shared_positions,
            )
            singleton = synthesize_contextual_expression(
                single_fields,
                tuple(composition_constants),
                single_examples,
                max_depth=int(composition_max_depth),
                max_candidates=per_pair,
            )
            total_singleton_candidates += singleton.candidates_considered
            singleton_passed.append(singleton.passed)
            singleton_counts.append(singleton.candidates_considered)
        if any(singleton_passed):
            continue

        selection_values = tuple(evaluate_expr(composition.expression, row.context) for row in examples)
        exact = sum(
            _equivalent(actual, expected)
            for actual, expected in zip(selection_values, selection_targets, strict=True)
        )
        if exact != len(selection_targets):
            continue

        interventions = (left.intervention, right.intervention)
        digest = expr_digest(composition.expression)
        program = ContextualCompositionProgram(
            interventions,
            shared_positions,
            composition.expression,
            digest,
            _program_id(interventions, shared_positions, composition.expression),
        )
        passing.append(ContextualCompositionCandidate(
            program,
            left,
            right,
            used,
            len(selection_targets),
            exact,
            False,
            tuple(fixed_rows),
            (False, False),
            tuple(singleton_counts),
            composition.candidates_considered,
        ))

    passing.sort(key=lambda row: (
        row.program.composition_expression.depth,
        row.program.composition_expression.cost,
        tuple(sorted((_profile_semantic_id(row.left_profile), _profile_semantic_id(row.right_profile)))),
        row.program.composition_digest,
        row.program.interventions[0].intervention_id,
        row.program.interventions[1].intervention_id,
    ))
    selected = passing[0] if passing else None
    return ContextualCompositionStructureReceipt(
        selected is not None,
        selected,
        len(passing),
        len(profiles),
        invalid_rejected,
        degenerate_rejected,
        len(specs),
        total_composition_candidates,
        total_singleton_candidates,
        oracle_calls,
        0,
        'contextual_composition_discovered' if selected is not None else (
            'composition_budget_exhausted' if exhausted else 'no_contextual_composition'
        ),
        0,
    )


def _project_context(
    schema: PositionalSchema,
    context: Mapping[str, object],
    free_positions: tuple[int, ...],
) -> dict[str, object]:
    canonical = schema.to_canonical_context(context)
    return {schema.canonical_fields[index]: canonical[schema.canonical_fields[index]] for index in free_positions}


def _rewrite_with_mapping(expr: Expr, mapping: Mapping[str, Expr]) -> Expr:
    if isinstance(expr, Field):
        return mapping.get(expr.name, expr)
    if isinstance(expr, Const):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _rewrite_with_mapping(expr.arg, mapping))
    if isinstance(expr, Binary):
        return Binary(expr.op, _rewrite_with_mapping(expr.left, mapping), _rewrite_with_mapping(expr.right, mapping))
    if isinstance(expr, IfElse):
        return IfElse(
            _rewrite_with_mapping(expr.condition, mapping),
            _rewrite_with_mapping(expr.when_true, mapping),
            _rewrite_with_mapping(expr.when_false, mapping),
        )
    raise TypeError(f'unsupported expression node: {type(expr).__name__}')


@dataclass(frozen=True, slots=True)
class ContextualCompositionSynthesisReceipt:
    passed: bool
    structure: ContextualCompositionStructureReceipt
    expression: Expr | None
    probe_expressions: tuple[Expr, ...]
    probe_candidates_considered: tuple[int, ...]
    probe_validation_cases: int
    probe_validation_exact: int
    final_validation_cases: int
    final_validation_exact: int
    reason: str
    trainable_parameter_count: int = 0


def synthesize_contextual_composition_program(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    program_need: OperatorInventionNeed,
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_constants: Sequence[object] = (0.0,),
    composition_max_depth: int = 2,
    composition_max_candidates_per_pair: int = 12000,
    max_composition_candidates_total: int = 120000,
    probe_constants: Sequence[object] = (0.0,),
    probe_max_depth: int = 3,
    probe_max_candidates: int = 20000,
) -> ContextualCompositionSynthesisReceipt:
    if not isinstance(program_need, OperatorInventionNeed):
        raise TypeError('program_need must be OperatorInventionNeed')
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    if set(schema.field_names) != set(program_need.field_names):
        raise ValueError('ordered_field_names must match program_need fields')
    anchors = derive_anchor_values(program_need, min_count=int(intervention_arity))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    structure = discover_contextual_composition_structure(
        oracle,
        schema.field_names,
        anchors,
        discovery,
        validation,
        context_validator=context_validator,
        intervention_arity=int(intervention_arity),
        composition_constants=tuple(composition_constants),
        composition_max_depth=int(composition_max_depth),
        composition_max_candidates_per_pair=int(composition_max_candidates_per_pair),
        max_composition_candidates_total=int(max_composition_candidates_total),
    )
    if not structure.passed or structure.selected is None:
        return ContextualCompositionSynthesisReceipt(
            False, structure, None, (), (), len(validation), 0, len(validation), 0,
            'structure_discovery_failed', 0,
        )

    selected = structure.selected
    probe_exprs_canonical: list[Expr] = []
    probe_exprs_external: list[Expr] = []
    probe_counts: list[int] = []
    probe_validation_exact = 0

    for profile in (selected.left_profile, selected.right_profile):
        fixed = {position for position, _value in profile.intervention.bindings}
        free_positions = tuple(index for index in range(len(schema.field_names)) if index not in fixed)
        fields = tuple(schema.canonical_fields[index] for index in free_positions)
        examples = tuple(
            OperatorExample(
                f'probe:{index}',
                _project_context(schema, context, free_positions),
                expected,
            )
            for index, (context, expected) in enumerate(zip(discovery, profile.discovery_outputs, strict=True))
        )
        probe = synthesize_contextual_expression(
            fields,
            tuple(probe_constants),
            examples,
            max_depth=int(probe_max_depth),
            max_candidates=int(probe_max_candidates),
        )
        probe_counts.append(probe.candidates_considered)
        if not probe.passed or probe.expression is None:
            return ContextualCompositionSynthesisReceipt(
                False, structure, None, tuple(probe_exprs_external), tuple(probe_counts),
                len(validation), probe_validation_exact, len(validation), 0,
                'probe_synthesis_failed', 0,
            )
        probe_exprs_canonical.append(probe.expression)
        external = schema.externalize_expr(probe.expression)
        probe_exprs_external.append(external)
        for context, expected in zip(validation, profile.validation_outputs, strict=True):
            try:
                actual = evaluate_expr(external, context)
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                actual = object()
            probe_validation_exact += int(_equivalent(actual, expected))

    if probe_validation_exact != len(validation) * 2:
        return ContextualCompositionSynthesisReceipt(
            False, structure, None, tuple(probe_exprs_external), tuple(probe_counts),
            len(validation), probe_validation_exact, len(validation), 0,
            'probe_validation_failed', 0,
        )

    mapping: dict[str, Expr] = {
        '__p0': probe_exprs_canonical[0],
        '__p1': probe_exprs_canonical[1],
    }
    composed_canonical = _rewrite_with_mapping(selected.program.composition_expression, mapping)
    expression = schema.externalize_expr(composed_canonical)
    final_exact = 0
    try:
        for context in validation:
            expected = _oracle_value(oracle, context)
            actual = evaluate_expr(expression, context)
            final_exact += int(_equivalent(actual, expected))
    except Exception:
        return ContextualCompositionSynthesisReceipt(
            False, structure, expression, tuple(probe_exprs_external), tuple(probe_counts),
            len(validation), probe_validation_exact, len(validation), final_exact,
            'final_validation_error', 0,
        )
    if final_exact != len(validation):
        return ContextualCompositionSynthesisReceipt(
            False, structure, expression, tuple(probe_exprs_external), tuple(probe_counts),
            len(validation), probe_validation_exact, len(validation), final_exact,
            'final_validation_failed', 0,
        )
    return ContextualCompositionSynthesisReceipt(
        True,
        structure,
        expression,
        tuple(probe_exprs_external),
        tuple(probe_counts),
        len(validation),
        probe_validation_exact,
        len(validation),
        final_exact,
        'contextual_program_synthesized',
        0,
    )


__all__ = [
    'ContextualExpressionReceipt',
    'ContextualInterventionProfile',
    'ContextualCompositionProgram',
    'ContextualCompositionCandidate',
    'ContextualCompositionStructureReceipt',
    'ContextualCompositionSynthesisReceipt',
    'synthesize_contextual_expression',
    'discover_contextual_composition_structure',
    'synthesize_contextual_composition_program',
]
