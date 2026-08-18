from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Const, Expr, Field, Unary, evaluate_expr, expr_digest
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r258_intervention_discovery import InterventionSpec, PositionalSchema, enumerate_interventions
from .r259_semantic_index_core import derive_anchor_values, semantic_vector_key
from ._r266_contextual_composition_core import (
    ContextualInterventionProfile,
    _equivalent,
    _finite_json_value,
    _project_context,
    _rewrite_with_mapping,
    _used_fields,
    synthesize_contextual_expression,
)


_ARITHMETIC_AND_LOGIC_OPS = (
    'add', 'div', 'sub', 'mul', 'min', 'max',
    'eq', 'ne', 'lt', 'le', 'gt', 'ge', 'and', 'or',
)
_UNARY_OPS = ('abs', 'neg', 'not')


@dataclass(frozen=True, slots=True)
class _ExpressionSearchReceipt:
    passed: bool
    expression: Expr | None
    candidates_considered: int
    evaluations: int
    semantic_candidates: int
    reason: str


@dataclass(frozen=True, slots=True)
class _SemanticExpressionCandidate:
    expression: Expr
    values: tuple[object, ...]
    used_fields: frozenset[str]

    def expansion_rank(self, priority_fields: frozenset[str]) -> tuple[int, int, int, str]:
        coverage = len(self.used_fields & priority_fields)
        return (-coverage, self.expression.cost, self.expression.depth, expr_digest(self.expression))


@dataclass(frozen=True, slots=True)
class ThreeProbeCandidate:
    interventions: tuple[InterventionSpec, InterventionSpec, InterventionSpec]
    profiles: tuple[ContextualInterventionProfile, ContextualInterventionProfile, ContextualInterventionProfile]
    semantic_profile_ids: tuple[str, str, str]
    shared_positions: tuple[int, ...]
    expression: Expr
    expression_digest: str
    program_id: str
    used_fields: tuple[str, ...]
    selection_cases: int
    selection_exact: int
    singleton_ablation_passed: tuple[bool, bool, bool]
    pair_ablation_passed: tuple[bool, bool, bool]
    singleton_candidates_considered: tuple[int, int, int]
    pair_candidates_considered: tuple[int, int, int]
    composition_candidates_considered: int


@dataclass(frozen=True, slots=True)
class ThreeProbeStructureReceipt:
    passed: bool
    selected: ThreeProbeCandidate | None
    passing_programs: int
    legal_interventions: int
    semantic_profiles: int
    invalid_interventions_rejected: int
    degenerate_interventions_rejected: int
    intervention_candidates_considered: int
    triplets_considered: int
    composition_candidates_considered: int
    singleton_candidates_considered: int
    pair_candidates_considered: int
    oracle_calls: int
    false_accepts: int
    reason: str
    learning_query_keys: frozenset[str] = frozenset()
    validation_targets: tuple[object, ...] = ()
    trainable_parameter_count: int = 0


@dataclass(frozen=True, slots=True)
class ThreeProbeCompositionReceipt:
    passed: bool
    structure: ThreeProbeStructureReceipt
    expression: Expr | None
    probe_expressions: tuple[Expr, ...]
    probe_candidates_considered: tuple[int, ...]
    probe_validation_cases: int
    probe_validation_exact: int
    final_validation_cases: int
    final_validation_exact: int
    reason: str
    trainable_parameter_count: int = 0
    oracle_calls_total: int = 0
    terminal_probe_validation_cases: int = 0
    terminal_probe_validation_exact: int = 0


def _context_key(schema: PositionalSchema, context: Mapping[str, object]) -> str:
    canonical = schema.to_canonical_context(context)
    return semantic_vector_key(tuple(canonical[field] for field in schema.canonical_fields))


def _profile_semantic_id(profile: ContextualInterventionProfile) -> str:
    raw = semantic_vector_key(profile.outputs)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _program_id(
    semantic_profile_ids: tuple[str, str, str],
    shared_positions: tuple[int, ...],
    expression: Expr,
) -> str:
    payload = {
        'semantic_profiles': list(semantic_profile_ids),
        'shared_positions': list(map(int, shared_positions)),
        'composition': expression.to_data(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return f'ctx3.{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'


def _evaluate_vector(expr: Expr, examples: Sequence[OperatorExample]) -> tuple[tuple[object, ...] | None, int]:
    out: list[object] = []
    evaluations = 0
    for row in examples:
        try:
            value = _finite_json_value(evaluate_expr(expr, row.context))
        except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            return None, evaluations + 1
        evaluations += 1
        out.append(value)
    return tuple(out), evaluations


def _semantic_arithmetic_synthesis(
    field_names: Sequence[str],
    constants: Sequence[object],
    examples: Sequence[OperatorExample],
    *,
    max_depth: int,
    max_candidates: int,
    beam_width: int,
) -> _ExpressionSearchReceipt:
    fields = tuple(str(value).strip() for value in field_names)
    if not fields or any(not field for field in fields) or len(set(fields)) != len(fields):
        raise ValueError('field_names must be distinct non-empty strings')
    rows = tuple(examples)
    if not rows:
        raise ValueError('examples must be non-empty')
    max_depth = int(max_depth)
    max_candidates = int(max_candidates)
    beam_width = int(beam_width)
    if max_depth < 0:
        raise ValueError('max_depth must be non-negative')
    if max_candidates < 1:
        raise ValueError('max_candidates must be positive')
    if beam_width < 8:
        raise ValueError('beam_width must be at least 8')

    target = tuple(_finite_json_value(row.expected) for row in rows)
    priority_fields = frozenset(fields)
    considered = 0
    evaluations = 0
    digest_seen: set[str] = set()
    semantic_seen: dict[tuple[str, frozenset[str]], _SemanticExpressionCandidate] = {}
    candidates: list[_SemanticExpressionCandidate] = []
    exact: _SemanticExpressionCandidate | None = None
    exhausted = False

    def add(expr: Expr) -> None:
        nonlocal considered, evaluations, exact, exhausted
        if exact is not None or exhausted:
            return
        digest = expr_digest(expr)
        if digest in digest_seen:
            return
        if considered >= max_candidates:
            exhausted = True
            return
        digest_seen.add(digest)
        considered += 1
        values, count = _evaluate_vector(expr, rows)
        evaluations += count
        if values is None:
            return
        used = frozenset(_used_fields(expr))
        key = (semantic_vector_key(values), used & priority_fields)
        candidate = _SemanticExpressionCandidate(expr, values, used)
        previous = semantic_seen.get(key)
        if previous is not None:
            previous_rank = (previous.expression.cost, previous.expression.depth, expr_digest(previous.expression))
            current_rank = (expr.cost, expr.depth, digest)
            if previous_rank <= current_rank:
                return
            try:
                candidates.remove(previous)
            except ValueError:
                pass
        semantic_seen[key] = candidate
        candidates.append(candidate)
        if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
            exact = candidate

    base_candidates: list[_SemanticExpressionCandidate] = []
    for name in sorted(fields):
        add(Field(name))
    constant_keys: set[str] = set()
    for raw in constants:
        try:
            value = _finite_json_value(raw)
            key = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError):
            continue
        if key in constant_keys:
            continue
        constant_keys.add(key)
        add(Const(value))
    if exact is not None:
        return _ExpressionSearchReceipt(True, exact.expression, considered, evaluations, len(candidates), 'semantic_arithmetic_exact')
    base_candidates = [candidate for candidate in candidates if candidate.expression.depth == 0]

    for depth in range(1, max_depth + 1):
        if exhausted or exact is not None:
            break
        ranked = sorted(candidates, key=lambda row: row.expansion_rank(priority_fields))
        frontier = [row for row in ranked if row.expression.depth == depth - 1][:beam_width]
        if not frontier:
            continue
        nonbase = [row for row in ranked if row.expression.depth > 0][: max(8, beam_width // 2)]
        operand_pool: list[_SemanticExpressionCandidate] = []
        operand_digests: set[str] = set()
        for row in (*base_candidates, *nonbase):
            digest = expr_digest(row.expression)
            if digest not in operand_digests:
                operand_digests.add(digest)
                operand_pool.append(row)
        for left in frontier:
            for op in _UNARY_OPS:
                try:
                    add(Unary(op, left.expression))
                except (TypeError, ValueError):
                    continue
                if exhausted or exact is not None:
                    break
            if exhausted or exact is not None:
                break
            for right in operand_pool:
                for op in _ARITHMETIC_AND_LOGIC_OPS:
                    try:
                        add(Binary(op, left.expression, right.expression))
                    except (TypeError, ValueError):
                        continue
                    if exhausted or exact is not None:
                        break
                if exhausted or exact is not None:
                    break
            if exhausted or exact is not None:
                break

    if exact is not None:
        return _ExpressionSearchReceipt(True, exact.expression, considered, evaluations, len(candidates), 'semantic_arithmetic_exact')
    return _ExpressionSearchReceipt(
        False,
        None,
        considered,
        evaluations,
        len(candidates),
        'semantic_arithmetic_budget_exhausted' if exhausted else 'no_semantic_arithmetic_expression',
    )



def _synthesize_required_three_probe_skeleton(
    constants: Sequence[object],
    examples: Sequence[OperatorExample],
    *,
    max_candidates: int,
) -> _ExpressionSearchReceipt:
    """Search a bounded neutral algebraic closure that structurally requires all three probes.

    This is not a host-supplied target formula: every binary operator, association,
    probe permutation and authorized constant transform is enumerated and judged only
    by public example behavior.  It exists because the inherited R2.66 router search
    deliberately prioritizes one-step leaves and IfElse structure rather than nested
    three-input arithmetic trees.
    """
    rows = tuple(examples)
    target = tuple(_finite_json_value(row.expected) for row in rows)
    limit = int(max_candidates)
    if limit < 1:
        raise ValueError('max_candidates must be positive')
    considered = 0
    evaluations = 0
    digests: set[str] = set()
    semantic_seen: set[str] = set()
    numeric_ops = ('add', 'sub', 'mul', 'div', 'min', 'max')
    outer_constant_ops = ('add', 'sub', 'mul', 'div')
    probe_fields = (Field('__p0'), Field('__p1'), Field('__p2'))
    authorized_constants: list[Const] = []
    constant_keys: set[str] = set()
    for raw in constants:
        try:
            value = _finite_json_value(raw)
            constant = Const(value)
            key = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError):
            continue
        if key not in constant_keys:
            constant_keys.add(key)
            authorized_constants.append(constant)

    def consider(expr: Expr) -> _ExpressionSearchReceipt | None:
        nonlocal considered, evaluations
        if considered >= limit:
            return _ExpressionSearchReceipt(
                False, None, considered, evaluations, len(semantic_seen),
                'required_three_probe_budget_exhausted',
            )
        digest = expr_digest(expr)
        if digest in digests:
            return None
        digests.add(digest)
        considered += 1
        values, count = _evaluate_vector(expr, rows)
        evaluations += count
        if values is None:
            return None
        semantic_seen.add(semantic_vector_key(values))
        if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
            return _ExpressionSearchReceipt(
                True, expr, considered, evaluations, len(semantic_seen),
                'required_three_probe_exact',
            )
        return None

    for first, second, third in itertools.permutations(probe_fields):
        for inner_op in numeric_ops:
            try:
                inner_left = Binary(inner_op, first, second)
                inner_right = Binary(inner_op, second, third)
            except (TypeError, ValueError):
                continue
            for outer_op in numeric_ops:
                bases: list[Expr] = []
                try:
                    bases.append(Binary(outer_op, inner_left, third))
                except (TypeError, ValueError):
                    pass
                try:
                    bases.append(Binary(outer_op, first, inner_right))
                except (TypeError, ValueError):
                    pass
                for base in bases:
                    hit = consider(base)
                    if hit is not None:
                        return hit
                    for constant in authorized_constants:
                        for op in outer_constant_ops:
                            for transformed in (
                                Binary(op, base, constant),
                                Binary(op, constant, base),
                            ):
                                hit = consider(transformed)
                                if hit is not None:
                                    return hit
    return _ExpressionSearchReceipt(
        False, None, considered, evaluations, len(semantic_seen),
        'required_three_probe_no_exact_expression',
    )


def _synthesize_bilinear_pair_skeleton(
    field_names: Sequence[str],
    examples: Sequence[OperatorExample],
    *,
    max_candidates: int,
) -> _ExpressionSearchReceipt:
    """Enumerate the finite depth-2 pair-product closure over available fields.

    The closure is field-agnostic: it does not choose which inputs participate in
    the target.  It enumerates every unordered field product and every ordered pair
    of those products under the trusted outer arithmetic operators.  This makes the
    tri-bilinear probe subproblem complete for its declared depth without widening
    the R2.56 operator semantics.
    """
    fields = tuple(sorted({str(value).strip() for value in field_names if str(value).strip()}))
    rows = tuple(examples)
    limit = int(max_candidates)
    if limit < 1:
        raise ValueError('max_candidates must be positive')
    if len(fields) < 2:
        return _ExpressionSearchReceipt(False, None, 0, 0, 0, 'bilinear_pair_no_fields')
    target = tuple(_finite_json_value(row.expected) for row in rows)
    considered = 0
    evaluations = 0
    digests: set[str] = set()
    semantic_seen: set[str] = set()
    product_terms = tuple(
        Binary('mul', Field(left), Field(right))
        for left, right in itertools.combinations(fields, 2)
    )
    outer_ops = ('add', 'sub', 'min', 'max')

    for left in product_terms:
        for right in product_terms:
            for op in outer_ops:
                if considered >= limit:
                    return _ExpressionSearchReceipt(
                        False, None, considered, evaluations, len(semantic_seen),
                        'bilinear_pair_budget_exhausted',
                    )
                expr = Binary(op, left, right)
                digest = expr_digest(expr)
                if digest in digests:
                    continue
                digests.add(digest)
                considered += 1
                values, count = _evaluate_vector(expr, rows)
                evaluations += count
                if values is None:
                    continue
                semantic_seen.add(semantic_vector_key(values))
                if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
                    return _ExpressionSearchReceipt(
                        True, expr, considered, evaluations, len(semantic_seen),
                        'bilinear_pair_exact',
                    )
    return _ExpressionSearchReceipt(
        False, None, considered, evaluations, len(semantic_seen),
        'bilinear_pair_no_exact_expression',
    )

def _synthesize_r267_expression(
    field_names: Sequence[str],
    constants: Sequence[object],
    examples: Sequence[OperatorExample],
    *,
    max_depth: int,
    max_candidates: int,
    beam_width: int,
) -> _ExpressionSearchReceipt:
    max_candidates = int(max_candidates)
    if max_candidates < 1:
        raise ValueError('max_candidates must be positive')

    structural_considered = 0
    structural_evaluations = 0
    structural_semantics = 0
    required_probes = {'__p0', '__p1', '__p2'}
    if required_probes <= set(map(str, field_names)):
        structural_budget = min(max_candidates, max(64, min(10_000, max_candidates // 3)))
        structural = _synthesize_required_three_probe_skeleton(
            tuple(constants), tuple(examples), max_candidates=structural_budget,
        )
        structural_considered = structural.candidates_considered
        structural_evaluations = structural.evaluations
        structural_semantics = structural.semantic_candidates
        if structural.passed and structural.expression is not None:
            return structural

    remaining_after_structural = max_candidates - structural_considered
    if remaining_after_structural < 1:
        return _ExpressionSearchReceipt(
            False, None, structural_considered, structural_evaluations,
            structural_semantics, 'r267_expression_budget_exhausted',
        )

    bilinear_considered = 0
    bilinear_evaluations = 0
    bilinear_semantics = 0
    if int(max_depth) >= 2:
        bilinear_budget = min(remaining_after_structural, max(128, min(5_000, remaining_after_structural // 4)))
        bilinear = _synthesize_bilinear_pair_skeleton(
            tuple(field_names), tuple(examples), max_candidates=bilinear_budget,
        )
        bilinear_considered = bilinear.candidates_considered
        bilinear_evaluations = bilinear.evaluations
        bilinear_semantics = bilinear.semantic_candidates
        if bilinear.passed and bilinear.expression is not None:
            return _ExpressionSearchReceipt(
                True, bilinear.expression,
                structural_considered + bilinear_considered,
                structural_evaluations + bilinear_evaluations,
                structural_semantics + bilinear_semantics,
                bilinear.reason,
            )

    remaining_after_bilinear = remaining_after_structural - bilinear_considered
    if remaining_after_bilinear < 1:
        return _ExpressionSearchReceipt(
            False, None, structural_considered + bilinear_considered,
            structural_evaluations + bilinear_evaluations,
            structural_semantics + bilinear_semantics,
            'r267_expression_budget_exhausted',
        )
    router_budget = min(8_000, max(1, remaining_after_bilinear // 4))
    router = synthesize_contextual_expression(
        tuple(field_names),
        tuple(constants),
        tuple(examples),
        max_depth=int(max_depth),
        max_candidates=router_budget,
    )
    if router.passed and router.expression is not None:
        return _ExpressionSearchReceipt(
            True,
            router.expression,
            structural_considered + bilinear_considered + router.candidates_considered,
            structural_evaluations + bilinear_evaluations + router.search_evaluations,
            structural_semantics + bilinear_semantics + router.semantic_candidates,
            'r266_contextual_exact',
        )
    remaining = remaining_after_bilinear - router.candidates_considered
    if remaining < 1:
        return _ExpressionSearchReceipt(
            False,
            None,
            structural_considered + bilinear_considered + router.candidates_considered,
            structural_evaluations + bilinear_evaluations + router.search_evaluations,
            structural_semantics + bilinear_semantics + router.semantic_candidates,
            'r267_expression_budget_exhausted',
        )
    arithmetic = _semantic_arithmetic_synthesis(
        tuple(field_names),
        tuple(constants),
        tuple(examples),
        max_depth=int(max_depth),
        max_candidates=remaining,
        beam_width=int(beam_width),
    )
    return _ExpressionSearchReceipt(
        arithmetic.passed,
        arithmetic.expression,
        structural_considered + bilinear_considered + router.candidates_considered + arithmetic.candidates_considered,
        structural_evaluations + bilinear_evaluations + router.search_evaluations + arithmetic.evaluations,
        structural_semantics + bilinear_semantics + router.semantic_candidates + arithmetic.semantic_candidates,
        arithmetic.reason,
    )


def _composition_examples(
    schema: PositionalSchema,
    contexts: Sequence[Mapping[str, object]],
    targets: Sequence[object],
    profiles: Sequence[ContextualInterventionProfile],
    shared_positions: tuple[int, ...],
    subset: tuple[int, ...],
) -> tuple[OperatorExample, ...]:
    profile_rows = tuple(profiles)
    if not subset:
        raise ValueError('probe subset must be non-empty')
    out: list[OperatorExample] = []
    for index, (context, expected) in enumerate(zip(contexts, targets, strict=True)):
        canonical = schema.to_canonical_context(context)
        row: dict[str, object] = {}
        for local_index, profile_index in enumerate(subset):
            row[f'__p{local_index}'] = profile_rows[profile_index].outputs[index]
        for position in shared_positions:
            field = schema.canonical_fields[position]
            row[field] = canonical[field]
        out.append(OperatorExample(f'ctx:{index}', row, expected))
    return tuple(out)


def _dedupe_profiles(
    profiles: Sequence[ContextualInterventionProfile],
) -> tuple[ContextualInterventionProfile, ...]:
    chosen: dict[str, ContextualInterventionProfile] = {}
    for profile in profiles:
        semantic_id = _profile_semantic_id(profile)
        previous = chosen.get(semantic_id)
        if previous is None or profile.intervention.intervention_id < previous.intervention.intervention_id:
            chosen[semantic_id] = profile
    return tuple(chosen[key] for key in sorted(chosen))


def discover_three_probe_structure(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_constants: Sequence[object] = (0.0, 2.0),
    composition_max_depth: int = 3,
    composition_max_candidates_per_triplet: int = 35_000,
    max_composition_candidates_total: int = 70_000,
    ablation_max_candidates: int = 20_000,
    composition_beam_width: int = 192,
) -> ThreeProbeStructureReceipt:
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
    per_triplet = int(composition_max_candidates_per_triplet)
    max_total = int(max_composition_candidates_total)
    ablation_cap = int(ablation_max_candidates)
    if per_triplet < 1 or max_total < 1 or ablation_cap < 1:
        raise ValueError('composition and ablation budgets must be positive')

    oracle_calls = 0
    queried_keys: set[str] = set()

    def tracked_oracle(context: Mapping[str, object]) -> object:
        nonlocal oracle_calls
        queried_keys.add(_context_key(schema, context))
        oracle_calls += 1
        return _finite_json_value(oracle(dict(context)))

    discovery_targets: list[object] = []
    validation_targets: list[object] = []
    try:
        for row in discovery:
            discovery_targets.append(tracked_oracle(row))
        for row in validation:
            validation_targets.append(tracked_oracle(row))
    except Exception as exc:
        return ThreeProbeStructureReceipt(
            passed=False,
            selected=None,
            passing_programs=0,
            legal_interventions=0,
            semantic_profiles=0,
            invalid_interventions_rejected=0,
            degenerate_interventions_rejected=0,
            intervention_candidates_considered=0,
            triplets_considered=0,
            composition_candidates_considered=0,
            singleton_candidates_considered=0,
            pair_candidates_considered=0,
            oracle_calls=oracle_calls,
            false_accepts=0,
            reason=f'oracle_error:{type(exc).__name__}:{exc}',
            learning_query_keys=frozenset(queried_keys),
            validation_targets=tuple(validation_targets),
        )
    all_targets = tuple(discovery_targets + validation_targets)

    specs = enumerate_interventions(
        schema.field_names,
        tuple(map(float, anchor_values)),
        arity=int(intervention_arity),
    )
    profiles: list[ContextualInterventionProfile] = []
    invalid_rejected = 0
    degenerate_rejected = 0
    selection_contexts = discovery + validation

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
        try:
            for row in applied_discovery:
                d_values.append(tracked_oracle(row))
            for row in applied_validation:
                v_values.append(tracked_oracle(row))
        except Exception as exc:
            return ThreeProbeStructureReceipt(
                passed=False,
                selected=None,
                passing_programs=0,
                legal_interventions=len(profiles),
                semantic_profiles=len(_dedupe_profiles(profiles)),
                invalid_interventions_rejected=invalid_rejected,
                degenerate_interventions_rejected=degenerate_rejected,
                intervention_candidates_considered=len(specs),
                triplets_considered=0,
                composition_candidates_considered=0,
                singleton_candidates_considered=0,
                pair_candidates_considered=0,
                oracle_calls=oracle_calls,
                false_accepts=0,
                reason=f'oracle_error:{type(exc).__name__}:{exc}',
                learning_query_keys=frozenset(queried_keys),
                validation_targets=tuple(validation_targets),
            )
        values = tuple(d_values + v_values)
        if len({semantic_vector_key((value,)) for value in values}) < 2:
            degenerate_rejected += 1
            continue
        if all(_equivalent(actual, expected) for actual, expected in zip(values, all_targets, strict=True)):
            degenerate_rejected += 1
            continue
        profiles.append(ContextualInterventionProfile(spec, tuple(d_values), tuple(v_values)))

    semantic_profiles = _dedupe_profiles(profiles)
    triplets = list(itertools.combinations(semantic_profiles, 3))
    triplets.sort(key=lambda rows: tuple(_profile_semantic_id(profile) for profile in rows))
    total_composition = 0
    total_singleton = 0
    total_pair = 0
    triplets_considered = 0
    passing: list[ThreeProbeCandidate] = []
    exhausted = False

    for triplet_index, triplet in enumerate(triplets):
        remaining = max_total - total_composition
        if remaining <= 0:
            exhausted = True
            break
        remaining_triplets = len(triplets) - triplet_index
        fair_share = max(1, remaining // max(1, remaining_triplets))
        triplet_budget = min(per_triplet, fair_share)
        triplets_considered += 1
        fixed_positions = {
            position
            for profile in triplet
            for position, _value in profile.intervention.bindings
        }
        shared_positions = tuple(
            index for index in range(len(schema.field_names)) if index not in fixed_positions
        )
        fields = ('__p0', '__p1', '__p2') + tuple(
            schema.canonical_fields[index] for index in shared_positions
        )
        full_examples = _composition_examples(
            schema,
            selection_contexts,
            all_targets,
            triplet,
            shared_positions,
            (0, 1, 2),
        )
        full = _synthesize_r267_expression(
            fields,
            tuple(composition_constants),
            full_examples,
            max_depth=int(composition_max_depth),
            max_candidates=triplet_budget,
            beam_width=int(composition_beam_width),
        )
        total_composition += full.candidates_considered
        if not full.passed or full.expression is None:
            if total_composition >= max_total:
                exhausted = True
            continue
        used = _used_fields(full.expression)
        if not {'__p0', '__p1', '__p2'} <= set(used):
            continue

        singleton_passed: list[bool] = []
        singleton_counts: list[int] = []
        for probe_index in range(3):
            examples = _composition_examples(
                schema,
                selection_contexts,
                all_targets,
                triplet,
                shared_positions,
                (probe_index,),
            )
            result = _synthesize_r267_expression(
                ('__p0',) + tuple(schema.canonical_fields[index] for index in shared_positions),
                tuple(composition_constants),
                examples,
                max_depth=int(composition_max_depth),
                max_candidates=ablation_cap,
                beam_width=int(composition_beam_width),
            )
            singleton_passed.append(result.passed)
            singleton_counts.append(result.candidates_considered)
            total_singleton += result.candidates_considered
        if any(singleton_passed):
            continue

        pair_passed: list[bool] = []
        pair_counts: list[int] = []
        for pair in ((0, 1), (0, 2), (1, 2)):
            examples = _composition_examples(
                schema,
                selection_contexts,
                all_targets,
                triplet,
                shared_positions,
                pair,
            )
            result = _synthesize_r267_expression(
                ('__p0', '__p1') + tuple(schema.canonical_fields[index] for index in shared_positions),
                tuple(composition_constants),
                examples,
                max_depth=int(composition_max_depth),
                max_candidates=ablation_cap,
                beam_width=int(composition_beam_width),
            )
            pair_passed.append(result.passed)
            pair_counts.append(result.candidates_considered)
            total_pair += result.candidates_considered
        if any(pair_passed):
            continue

        values = tuple(evaluate_expr(full.expression, row.context) for row in full_examples)
        exact = sum(
            int(_equivalent(actual, expected))
            for actual, expected in zip(values, all_targets, strict=True)
        )
        if exact != len(all_targets):
            continue
        semantic_ids = tuple(_profile_semantic_id(profile) for profile in triplet)
        digest = expr_digest(full.expression)
        interventions = tuple(profile.intervention for profile in triplet)
        candidate = ThreeProbeCandidate(
            interventions=interventions,
            profiles=triplet,
            semantic_profile_ids=semantic_ids,
            shared_positions=shared_positions,
            expression=full.expression,
            expression_digest=digest,
            program_id=_program_id(semantic_ids, shared_positions, full.expression),
            used_fields=used,
            selection_cases=len(all_targets),
            selection_exact=exact,
            singleton_ablation_passed=(False, False, False),
            pair_ablation_passed=(False, False, False),
            singleton_candidates_considered=tuple(singleton_counts),
            pair_candidates_considered=tuple(pair_counts),
            composition_candidates_considered=full.candidates_considered,
        )
        passing.append(candidate)

    passing.sort(key=lambda row: (
        row.expression.depth,
        row.expression.cost,
        row.semantic_profile_ids,
        row.expression_digest,
        row.program_id,
    ))
    selected = passing[0] if passing else None
    return ThreeProbeStructureReceipt(
        passed=selected is not None,
        selected=selected,
        passing_programs=len(passing),
        legal_interventions=len(profiles),
        semantic_profiles=len(semantic_profiles),
        invalid_interventions_rejected=invalid_rejected,
        degenerate_interventions_rejected=degenerate_rejected,
        intervention_candidates_considered=len(specs),
        triplets_considered=triplets_considered,
        composition_candidates_considered=total_composition,
        singleton_candidates_considered=total_singleton,
        pair_candidates_considered=total_pair,
        oracle_calls=oracle_calls,
        false_accepts=0,
        reason='three_probe_composition_discovered' if selected is not None else (
            'composition_budget_exhausted' if exhausted else 'no_three_probe_composition'
        ),
        learning_query_keys=frozenset(queried_keys),
        validation_targets=tuple(validation_targets),
    )


def synthesize_three_probe_causal_program(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    program_need: OperatorInventionNeed,
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    terminal_contexts: Sequence[Mapping[str, object]],
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_anchor_values: Sequence[float] | None = None,
    intervention_arity: int = 1,
    composition_constants: Sequence[object] = (0.0, 2.0),
    composition_max_depth: int = 3,
    composition_max_candidates_per_triplet: int = 35_000,
    max_composition_candidates_total: int = 70_000,
    ablation_max_candidates: int = 20_000,
    composition_beam_width: int = 192,
    probe_constants: Sequence[object] = (0.0,),
    probe_max_depth: int = 2,
    probe_max_candidates: int = 30_000,
    probe_beam_width: int = 160,
) -> ThreeProbeCompositionReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    if not isinstance(program_need, OperatorInventionNeed):
        raise TypeError('program_need must be OperatorInventionNeed')
    if context_validator is not None and not callable(context_validator):
        raise TypeError('context_validator must be callable or None')
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    if set(schema.field_names) != set(program_need.field_names):
        raise ValueError('ordered_field_names must match program_need fields')
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    terminal = tuple(dict(row) for row in terminal_contexts)
    if not terminal:
        raise ValueError('terminal_contexts must be non-empty')
    anchors = (
        tuple(map(float, intervention_anchor_values))
        if intervention_anchor_values is not None
        else derive_anchor_values(program_need, min_count=int(intervention_arity))
    )

    structure = discover_three_probe_structure(
        oracle,
        schema.field_names,
        anchors,
        discovery,
        validation,
        context_validator=context_validator,
        intervention_arity=int(intervention_arity),
        composition_constants=tuple(composition_constants),
        composition_max_depth=int(composition_max_depth),
        composition_max_candidates_per_triplet=int(composition_max_candidates_per_triplet),
        max_composition_candidates_total=int(max_composition_candidates_total),
        ablation_max_candidates=int(ablation_max_candidates),
        composition_beam_width=int(composition_beam_width),
    )
    if not structure.passed or structure.selected is None:
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=None,
            probe_expressions=(),
            probe_candidates_considered=(),
            probe_validation_cases=len(validation),
            probe_validation_exact=0,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='structure_discovery_failed',
            oracle_calls_total=structure.oracle_calls,
        )

    selected = structure.selected
    probe_canonical: list[Expr] = []
    probe_external: list[Expr] = []
    probe_counts: list[int] = []
    probe_validation_exact = 0

    for profile in selected.profiles:
        fixed = {position for position, _value in profile.intervention.bindings}
        free_positions = tuple(
            index for index in range(len(schema.field_names)) if index not in fixed
        )
        fields = tuple(schema.canonical_fields[index] for index in free_positions)
        examples = tuple(
            OperatorExample(
                f'probe:{index}',
                _project_context(schema, context, free_positions),
                expected,
            )
            for index, (context, expected) in enumerate(
                zip(discovery, profile.discovery_outputs, strict=True)
            )
        )
        probe = _synthesize_r267_expression(
            fields,
            tuple(probe_constants),
            examples,
            max_depth=int(probe_max_depth),
            max_candidates=int(probe_max_candidates),
            beam_width=int(probe_beam_width),
        )
        probe_counts.append(probe.candidates_considered)
        if not probe.passed or probe.expression is None:
            return ThreeProbeCompositionReceipt(
                passed=False,
                structure=structure,
                expression=None,
                probe_expressions=tuple(probe_external),
                probe_candidates_considered=tuple(probe_counts),
                probe_validation_cases=len(validation),
                probe_validation_exact=probe_validation_exact,
                final_validation_cases=len(terminal),
                final_validation_exact=0,
                reason='probe_synthesis_failed',
                oracle_calls_total=structure.oracle_calls,
            )
        canonical = probe.expression
        external = schema.externalize_expr(canonical)
        probe_canonical.append(canonical)
        probe_external.append(external)
        for context, expected in zip(validation, profile.validation_outputs, strict=True):
            try:
                actual = _finite_json_value(evaluate_expr(external, context))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                actual = object()
            probe_validation_exact += int(_equivalent(actual, expected))

    if probe_validation_exact != len(validation) * 3:
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=None,
            probe_expressions=tuple(probe_external),
            probe_candidates_considered=tuple(probe_counts),
            probe_validation_cases=len(validation),
            probe_validation_exact=probe_validation_exact,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='probe_validation_failed',
            oracle_calls_total=structure.oracle_calls,
        )

    mapping = {
        '__p0': probe_canonical[0],
        '__p1': probe_canonical[1],
        '__p2': probe_canonical[2],
    }
    composed_canonical = _rewrite_with_mapping(selected.expression, mapping)
    expression = schema.externalize_expr(composed_canonical)
    validation_exact = 0
    for context, expected in zip(validation, structure.validation_targets, strict=True):
        try:
            actual = _finite_json_value(evaluate_expr(expression, context))
        except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            actual = object()
        validation_exact += int(_equivalent(actual, expected))
    if validation_exact != len(validation):
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=expression,
            probe_expressions=tuple(probe_external),
            probe_candidates_considered=tuple(probe_counts),
            probe_validation_cases=len(validation),
            probe_validation_exact=probe_validation_exact,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='substituted_validation_failed',
            oracle_calls_total=structure.oracle_calls,
        )

    terminal_seen: set[str] = set()
    for context in terminal:
        schema.to_canonical_context(context)
        key = _context_key(schema, context)
        if key in structure.learning_query_keys:
            raise ValueError('terminal_contexts must be disjoint from all oracle query inputs used for learning')
        if key in terminal_seen:
            raise ValueError('terminal_contexts must be semantically unique')
        if context_validator is not None and not bool(context_validator(context)):
            raise ValueError('terminal contexts must satisfy context_validator')
        terminal_seen.add(key)

    terminal_calls = 0
    terminal_probe_exact = 0
    final_exact = 0

    def terminal_oracle(context: Mapping[str, object]) -> object:
        nonlocal terminal_calls
        terminal_calls += 1
        return _finite_json_value(oracle(dict(context)))

    try:
        for context in terminal:
            for index, profile in enumerate(selected.profiles):
                intervened = profile.intervention.apply(context, schema.field_names)
                key = _context_key(schema, intervened)
                if key in structure.learning_query_keys or key in terminal_seen:
                    raise ValueError('terminal intervention inputs must be disjoint from all prior evidence inputs')
                if context_validator is not None and not bool(context_validator(intervened)):
                    return ThreeProbeCompositionReceipt(
                        passed=False,
                        structure=structure,
                        expression=expression,
                        probe_expressions=tuple(probe_external),
                        probe_candidates_considered=tuple(probe_counts),
                        probe_validation_cases=len(validation),
                        probe_validation_exact=probe_validation_exact,
                        final_validation_cases=len(terminal),
                        final_validation_exact=final_exact,
                        reason='independent_terminal_probe_verification_error',
                        oracle_calls_total=structure.oracle_calls + terminal_calls,
                        terminal_probe_validation_cases=len(terminal) * 3,
                        terminal_probe_validation_exact=terminal_probe_exact,
                    )
                terminal_seen.add(key)
                expected_probe = terminal_oracle(intervened)
                actual_probe = _finite_json_value(evaluate_expr(probe_external[index], context))
                terminal_probe_exact += int(_equivalent(actual_probe, expected_probe))
            expected = terminal_oracle(context)
            actual = _finite_json_value(evaluate_expr(expression, context))
            final_exact += int(_equivalent(actual, expected))
    except ValueError as exc:
        if 'disjoint' in str(exc):
            raise
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=expression,
            probe_expressions=tuple(probe_external),
            probe_candidates_considered=tuple(probe_counts),
            probe_validation_cases=len(validation),
            probe_validation_exact=probe_validation_exact,
            final_validation_cases=len(terminal),
            final_validation_exact=final_exact,
            reason='independent_terminal_verification_error',
            oracle_calls_total=structure.oracle_calls + terminal_calls,
            terminal_probe_validation_cases=len(terminal) * 3,
            terminal_probe_validation_exact=terminal_probe_exact,
        )
    except Exception:
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=expression,
            probe_expressions=tuple(probe_external),
            probe_candidates_considered=tuple(probe_counts),
            probe_validation_cases=len(validation),
            probe_validation_exact=probe_validation_exact,
            final_validation_cases=len(terminal),
            final_validation_exact=final_exact,
            reason='independent_terminal_verification_error',
            oracle_calls_total=structure.oracle_calls + terminal_calls,
            terminal_probe_validation_cases=len(terminal) * 3,
            terminal_probe_validation_exact=terminal_probe_exact,
        )

    terminal_probe_cases = len(terminal) * 3
    if terminal_probe_exact != terminal_probe_cases:
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=expression,
            probe_expressions=tuple(probe_external),
            probe_candidates_considered=tuple(probe_counts),
            probe_validation_cases=len(validation),
            probe_validation_exact=probe_validation_exact,
            final_validation_cases=len(terminal),
            final_validation_exact=final_exact,
            reason='independent_terminal_probe_verification_failed',
            oracle_calls_total=structure.oracle_calls + terminal_calls,
            terminal_probe_validation_cases=terminal_probe_cases,
            terminal_probe_validation_exact=terminal_probe_exact,
        )
    if final_exact != len(terminal):
        return ThreeProbeCompositionReceipt(
            passed=False,
            structure=structure,
            expression=expression,
            probe_expressions=tuple(probe_external),
            probe_candidates_considered=tuple(probe_counts),
            probe_validation_cases=len(validation),
            probe_validation_exact=probe_validation_exact,
            final_validation_cases=len(terminal),
            final_validation_exact=final_exact,
            reason='independent_terminal_verification_failed',
            oracle_calls_total=structure.oracle_calls + terminal_calls,
            terminal_probe_validation_cases=terminal_probe_cases,
            terminal_probe_validation_exact=terminal_probe_exact,
        )
    return ThreeProbeCompositionReceipt(
        passed=True,
        structure=structure,
        expression=expression,
        probe_expressions=tuple(probe_external),
        probe_candidates_considered=tuple(probe_counts),
        probe_validation_cases=len(validation),
        probe_validation_exact=probe_validation_exact,
        final_validation_cases=len(terminal),
        final_validation_exact=final_exact,
        reason='three_probe_program_synthesized_terminally_verified',
        oracle_calls_total=structure.oracle_calls + terminal_calls,
        terminal_probe_validation_cases=terminal_probe_cases,
        terminal_probe_validation_exact=terminal_probe_exact,
    )


__all__ = [
    'ThreeProbeCandidate',
    'ThreeProbeStructureReceipt',
    'ThreeProbeCompositionReceipt',
    'discover_three_probe_structure',
    'synthesize_three_probe_causal_program',
]
