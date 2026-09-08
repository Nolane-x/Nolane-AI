from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

from .r256_operator_dsl import Const, Expr, Field
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary import AbstractionCall, CognitiveVocabulary, evaluate_with_vocabulary
from .r257_vocabulary_synthesis import synthesize_with_vocabulary


def _canonical_scalar(value: object) -> tuple[str, object]:
    if value is None or isinstance(value, (bool, int, str)):
        normalized = value
    elif isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            raise ValueError('constants must be finite JSON scalars')
        normalized = value
    else:
        raise TypeError('constants must be JSON scalar values')
    return json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=False), normalized


@dataclass(frozen=True, slots=True)
class ExposureSchema:
    abstraction_id: str
    target_param_index: int
    fixed_params: tuple[tuple[int, object], ...]
    validation_cases: int

    def __post_init__(self) -> None:
        aid = str(self.abstraction_id).strip()
        if not aid:
            raise ValueError('abstraction_id must be non-empty')
        target = int(self.target_param_index)
        if target < 0:
            raise ValueError('target_param_index must be non-negative')
        fixed = tuple(sorted((int(index), value) for index, value in self.fixed_params))
        if target in {index for index, _value in fixed}:
            raise ValueError('target parameter cannot also be fixed')
        if int(self.validation_cases) < 1:
            raise ValueError('validation_cases must be positive')
        object.__setattr__(self, 'abstraction_id', aid)
        object.__setattr__(self, 'target_param_index', target)
        object.__setattr__(self, 'fixed_params', fixed)
        object.__setattr__(self, 'validation_cases', int(self.validation_cases))


def discover_exposure_schemas(
    vocabulary: CognitiveVocabulary,
    *,
    constants: Iterable[object] = (0, 1, -1),
    probe_values: Iterable[object] = (-3, -1, 0, 0.25, 1, 2, 5),
) -> tuple[ExposureSchema, ...]:
    if not isinstance(vocabulary, CognitiveVocabulary):
        raise TypeError('vocabulary must be CognitiveVocabulary')

    constant_map: dict[str, object] = {}
    for value in constants:
        key, normalized = _canonical_scalar(value)
        constant_map[key] = normalized
    ordered_constants = tuple(constant_map[key] for key in sorted(constant_map))
    if not ordered_constants:
        raise ValueError('constants must be non-empty')

    probes = tuple(value for _key, value in sorted({_canonical_scalar(value) for value in probe_values}, key=lambda row: row[0]))
    if not probes:
        raise ValueError('probe_values must be non-empty')

    schemas: list[ExposureSchema] = []
    for abstraction in vocabulary.abstractions():
        if abstraction.parameter_count < 2:
            continue
        indices = tuple(range(abstraction.parameter_count))
        for target in indices:
            fixed_indices = tuple(index for index in indices if index != target)
            for fixed_values in itertools.product(ordered_constants, repeat=len(fixed_indices)):
                fixed = tuple(zip(fixed_indices, fixed_values))
                args = []
                fixed_map = dict(fixed)
                for index in indices:
                    args.append(Const(fixed_map[index]) if index in fixed_map else Field('__r258_exposed__'))
                call = AbstractionCall(abstraction.abstraction_id, tuple(args))
                valid = True
                for probe in probes:
                    try:
                        actual = evaluate_with_vocabulary(call, {'__r258_exposed__': probe}, vocabulary)
                    except (KeyError, TypeError, ValueError, OverflowError):
                        valid = False
                        break
                    if type(actual) is not type(probe) and not (
                        isinstance(actual, (int, float)) and not isinstance(actual, bool)
                        and isinstance(probe, (int, float)) and not isinstance(probe, bool)
                    ):
                        valid = False
                        break
                    if actual != probe:
                        valid = False
                        break
                if valid:
                    # Reject degenerate controls: every fixed assignment must be
                    # causally necessary for the identity exposure. If a control can
                    # vary across the validation grid while the output remains the
                    # target parameter, fixing it adds no information and only
                    # expands the later intervention search.
                    essential = True
                    for control_index, control_value in fixed:
                        control_breaks_identity = False
                        for alternate in probes:
                            if alternate == control_value:
                                continue
                            varied_args = []
                            for index in indices:
                                if index == target:
                                    varied_args.append(Field('__r258_exposed__'))
                                elif index == control_index:
                                    varied_args.append(Const(alternate))
                                else:
                                    varied_args.append(Const(fixed_map[index]))
                            varied_call = AbstractionCall(abstraction.abstraction_id, tuple(varied_args))
                            for probe in probes:
                                try:
                                    varied = evaluate_with_vocabulary(
                                        varied_call, {'__r258_exposed__': probe}, vocabulary,
                                    )
                                except (KeyError, TypeError, ValueError, OverflowError):
                                    control_breaks_identity = True
                                    break
                                if varied != probe:
                                    control_breaks_identity = True
                                    break
                            if control_breaks_identity:
                                break
                        if not control_breaks_identity:
                            essential = False
                            break
                    if essential:
                        schemas.append(ExposureSchema(
                            abstraction.abstraction_id,
                            target,
                            fixed,
                            len(probes),
                        ))

    schemas.sort(key=lambda row: (row.abstraction_id, row.target_param_index, row.fixed_params))
    return tuple(schemas)



@dataclass(frozen=True, slots=True)
class ProbeBudget:
    max_oracle_calls: int = 900
    max_interventions: int = 40
    subgoal_max_depth: int = 2
    subgoal_max_candidates: int = 12000
    max_cegis_rounds: int = 2

    def __post_init__(self) -> None:
        for name in ('max_oracle_calls', 'max_interventions', 'subgoal_max_candidates'):
            if int(getattr(self, name)) < 1:
                raise ValueError(f'{name} must be positive')
        if int(self.subgoal_max_depth) < 0:
            raise ValueError('subgoal_max_depth must be non-negative')
        if int(self.max_cegis_rounds) < 0:
            raise ValueError('max_cegis_rounds must be non-negative')
        object.__setattr__(self, 'max_oracle_calls', int(self.max_oracle_calls))
        object.__setattr__(self, 'max_interventions', int(self.max_interventions))
        object.__setattr__(self, 'subgoal_max_depth', int(self.subgoal_max_depth))
        object.__setattr__(self, 'subgoal_max_candidates', int(self.subgoal_max_candidates))
        object.__setattr__(self, 'max_cegis_rounds', int(self.max_cegis_rounds))


@dataclass(frozen=True, slots=True)
class ProbeAttemptReceipt:
    abstraction_id: str
    target_param_index: int
    fixed_field_values: tuple[tuple[str, object], ...]
    fixed_field_profile_ids: tuple[tuple[int, str], ...]
    remaining_fields: tuple[str, ...]
    oracle_calls_after: int
    subgoal_candidates_considered: int
    full_candidates_considered: int
    subgoal_passed: bool
    challenge_passed: bool
    full_passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ActiveProbeReceipt:
    passed: bool
    subgoal_expression: Expr | None
    full_expression: Expr | None
    abstraction_id: str
    target_param_index: int
    fixed_field_values: tuple[tuple[str, object], ...]
    fixed_field_profile_ids: tuple[tuple[int, str], ...]
    oracle_calls: int
    interventions_considered: int
    challenge_exact: int
    attempts: tuple[ProbeAttemptReceipt, ...]
    reason: str

    @property
    def fixed_fields(self) -> tuple[str, ...]:
        return tuple(field for field, _value in self.fixed_field_values)


class _OracleBudgetExhausted(RuntimeError):
    pass


class _InvalidOracleOutput(RuntimeError):
    pass


class _OracleQueryError(RuntimeError):
    pass


class _OracleLedger:
    def __init__(self, oracle: Callable[[Mapping[str, object]], object], max_calls: int) -> None:
        if not callable(oracle):
            raise TypeError('oracle must be callable')
        self.oracle = oracle
        self.max_calls = int(max_calls)
        self.calls = 0
        self._cache: dict[str, object] = {}

    @staticmethod
    def _context_key(context: Mapping[str, object]) -> str:
        try:
            return json.dumps(dict(context), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise _InvalidOracleOutput('oracle context is not finite JSON') from exc

    @staticmethod
    def _validate_output(value: object) -> object:
        try:
            json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise _InvalidOracleOutput('oracle output is not finite JSON') from exc
        return value

    def query(self, context: Mapping[str, object]) -> object:
        key = self._context_key(context)
        if key in self._cache:
            return self._cache[key]
        if self.calls >= self.max_calls:
            raise _OracleBudgetExhausted
        self.calls += 1
        try:
            value = self.oracle(dict(context))
        except Exception as exc:  # a proposed intervention may be outside the oracle domain
            raise _OracleQueryError(f'oracle raised {type(exc).__name__}') from exc
        value = self._validate_output(value)
        self._cache[key] = value
        return value


def _value_equal(left: object, right: object) -> bool:
    if (
        isinstance(left, (int, float)) and not isinstance(left, bool)
        and isinstance(right, (int, float)) and not isinstance(right, bool)
    ):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def _field_profile_id(field: str, contexts: Sequence[Mapping[str, object]]) -> str:
    values = []
    for context in contexts:
        if field not in context:
            raise KeyError(field)
        values.append(context[field])
    raw = json.dumps(values, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _dedupe_probe_rows(rows: Sequence[OperatorExample], field_names: Sequence[str]) -> tuple[OperatorExample, ...] | None:
    by_context: dict[str, OperatorExample] = {}
    for row in rows:
        projected = {field: row.context[field] for field in field_names}
        key = json.dumps(projected, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        existing = by_context.get(key)
        if existing is not None and not _value_equal(existing.expected, row.expected):
            return None
        by_context.setdefault(key, OperatorExample(row.name, projected, row.expected))
    return tuple(by_context[key] for key in sorted(by_context))


def _failure_receipt(reason: str, ledger: _OracleLedger, attempts: Sequence[ProbeAttemptReceipt]) -> ActiveProbeReceipt:
    return ActiveProbeReceipt(
        False, None, None, '', -1, (), (), ledger.calls, len(attempts), 0, tuple(attempts), reason,
    )


def discover_verified_subgoal(
    need: OperatorInventionNeed,
    training_examples: Sequence[OperatorExample],
    challenge_contexts: Sequence[Mapping[str, object]],
    vocabulary: CognitiveVocabulary,
    oracle: Callable[[Mapping[str, object]], object],
    *,
    budget: ProbeBudget = ProbeBudget(),
) -> ActiveProbeReceipt:
    if not isinstance(need, OperatorInventionNeed):
        raise TypeError('need must be OperatorInventionNeed')
    if not training_examples:
        raise ValueError('training_examples must be non-empty')
    if not challenge_contexts:
        raise ValueError('challenge_contexts must be non-empty')
    if not isinstance(vocabulary, CognitiveVocabulary):
        raise TypeError('vocabulary must be CognitiveVocabulary')
    if not isinstance(budget, ProbeBudget):
        raise TypeError('budget must be ProbeBudget')
    if not all(isinstance(row, OperatorExample) for row in training_examples):
        raise TypeError('training_examples must contain OperatorExample values')
    if not all(isinstance(row, Mapping) for row in challenge_contexts):
        raise TypeError('challenge_contexts must contain mappings')

    all_contexts = tuple(row.context for row in training_examples) + tuple(challenge_contexts)
    profile_ids = {field: _field_profile_id(field, all_contexts) for field in need.field_names}
    # Structural profiles lead ordering. Name is only a stable tie breaker when two
    # fields are observationally identical under the supplied contexts; those fields
    # are otherwise indistinguishable to this bounded learner.
    ordered_fields = tuple(sorted(need.field_names, key=lambda field: (profile_ids[field], field)))
    schemas = discover_exposure_schemas(vocabulary, constants=need.constants)
    ledger = _OracleLedger(oracle, budget.max_oracle_calls)
    attempts: list[ProbeAttemptReceipt] = []

    for schema in schemas:
        fixed_params = tuple(schema.fixed_params)
        fixed_values = tuple(value for _index, value in fixed_params)
        fixed_param_indices = tuple(index for index, _value in fixed_params)
        if len(fixed_params) >= len(ordered_fields):
            continue
        for selected_fields in itertools.permutations(ordered_fields, len(fixed_params)):
            if len(attempts) >= budget.max_interventions:
                break
            fixed_field_values = tuple(sorted(zip(selected_fields, fixed_values)))
            fixed_by_field = dict(fixed_field_values)
            remaining_fields = tuple(field for field in ordered_fields if field not in fixed_by_field)
            role_profiles = tuple(sorted(zip(fixed_param_indices, (profile_ids[field] for field in selected_fields))))

            try:
                probe_rows_raw = []
                for row_index, row in enumerate(training_examples):
                    transformed = dict(row.context)
                    transformed.update(fixed_by_field)
                    expected = ledger.query(transformed)
                    probe_rows_raw.append(OperatorExample(f'r258:train:{row_index}', transformed, expected))
            except _OracleBudgetExhausted:
                return _failure_receipt('oracle_budget_exhausted', ledger, attempts)
            except _InvalidOracleOutput:
                return _failure_receipt('invalid_oracle_output', ledger, attempts)
            except _OracleQueryError:
                attempts.append(ProbeAttemptReceipt(
                    schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                    remaining_fields, ledger.calls, 0, 0, False, False, False,
                    'oracle_domain_rejected_intervention',
                ))
                continue

            probe_rows = _dedupe_probe_rows(probe_rows_raw, remaining_fields)
            if probe_rows is None or len(probe_rows) < 2:
                attempts.append(ProbeAttemptReceipt(
                    schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                    remaining_fields, ledger.calls, 0, 0, False, False, False,
                    'non_functional_or_insufficient_projection',
                ))
                continue

            sub_need = OperatorInventionNeed(
                f'r258:latent:{schema.abstraction_id}:{schema.target_param_index}',
                remaining_fields,
                '__r258_latent__',
                constants=need.constants,
                max_depth=budget.subgoal_max_depth,
                max_candidates=budget.subgoal_max_candidates,
            )
            working_probe_rows = list(probe_rows)
            subgoal = synthesize_with_vocabulary(sub_need, tuple(working_probe_rows), vocabulary)
            total_subgoal_candidates = subgoal.candidates_considered
            if not subgoal.passed or subgoal.expression is None:
                attempts.append(ProbeAttemptReceipt(
                    schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                    remaining_fields, ledger.calls, total_subgoal_candidates, 0, False, False, False,
                    'latent_not_synthesized',
                ))
                continue

            challenge_ok = False
            challenge_exact = 0
            challenge_query_error = False
            for cegis_round in range(budget.max_cegis_rounds + 1):
                challenge_exact = 0
                first_failure: OperatorExample | None = None
                challenge_query_error = False
                try:
                    for challenge_index, context in enumerate(challenge_contexts):
                        transformed = dict(context)
                        transformed.update(fixed_by_field)
                        expected = ledger.query(transformed)
                        try:
                            actual = evaluate_with_vocabulary(subgoal.expression, transformed, vocabulary)
                        except (KeyError, TypeError, ValueError, OverflowError):
                            actual = None
                        if actual is not None and _value_equal(actual, expected):
                            challenge_exact += 1
                            continue
                        projected = {field: transformed[field] for field in remaining_fields}
                        first_failure = OperatorExample(
                            f'r258:cegis:{cegis_round}:{challenge_index}', projected, expected,
                        )
                        break
                except _OracleBudgetExhausted:
                    return _failure_receipt('oracle_budget_exhausted', ledger, attempts)
                except _InvalidOracleOutput:
                    return _failure_receipt('invalid_oracle_output', ledger, attempts)
                except _OracleQueryError:
                    challenge_query_error = True
                    break

                if challenge_query_error:
                    break
                if first_failure is None and challenge_exact == len(challenge_contexts):
                    challenge_ok = True
                    break
                if first_failure is None or cegis_round >= budget.max_cegis_rounds:
                    break
                candidate_rows = _dedupe_probe_rows(
                    tuple(working_probe_rows) + (first_failure,), remaining_fields,
                )
                if candidate_rows is None:
                    break
                working_probe_rows = list(candidate_rows)
                subgoal = synthesize_with_vocabulary(sub_need, tuple(working_probe_rows), vocabulary)
                total_subgoal_candidates += subgoal.candidates_considered
                if not subgoal.passed or subgoal.expression is None:
                    break

            if not challenge_ok or subgoal.expression is None:
                attempts.append(ProbeAttemptReceipt(
                    schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                    remaining_fields, ledger.calls, total_subgoal_candidates, 0, True, False, False,
                    'latent_challenge_failed',
                ))
                continue

            full = synthesize_with_vocabulary(
                need,
                training_examples,
                vocabulary,
                seed_expressions=(subgoal.expression,),
            )
            if not full.passed or full.expression is None:
                attempts.append(ProbeAttemptReceipt(
                    schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                    remaining_fields, ledger.calls, total_subgoal_candidates, full.candidates_considered,
                    True, True, False, 'seed_did_not_unlock_full_synthesis',
                ))
                continue

            final_exact = 0
            final_ok = True
            try:
                for context in challenge_contexts:
                    expected = ledger.query(context)
                    try:
                        actual = evaluate_with_vocabulary(full.expression, context, vocabulary)
                    except (KeyError, TypeError, ValueError, OverflowError):
                        final_ok = False
                        break
                    if _value_equal(actual, expected):
                        final_exact += 1
                    else:
                        final_ok = False
                        break
            except _OracleBudgetExhausted:
                return _failure_receipt('oracle_budget_exhausted', ledger, attempts)
            except _InvalidOracleOutput:
                return _failure_receipt('invalid_oracle_output', ledger, attempts)
            except _OracleQueryError:
                final_ok = False

            if not final_ok or final_exact != len(challenge_contexts):
                attempts.append(ProbeAttemptReceipt(
                    schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                    remaining_fields, ledger.calls, total_subgoal_candidates, full.candidates_considered,
                    True, True, False, 'full_challenge_failed',
                ))
                continue

            attempt = ProbeAttemptReceipt(
                schema.abstraction_id, schema.target_param_index, fixed_field_values, role_profiles,
                remaining_fields, ledger.calls, total_subgoal_candidates, full.candidates_considered,
                True, True, True, 'verified_causal_probe',
            )
            attempts.append(attempt)
            # The search order is deterministic from content-addressed schemas and
            # observation-profile field order. Once a candidate passes both the
            # intervention challenge and the original full-target challenge, further
            # oracle calls add cost without increasing the bounded acceptance claim.
            return ActiveProbeReceipt(
                True,
                subgoal.expression,
                full.expression,
                schema.abstraction_id,
                schema.target_param_index,
                fixed_field_values,
                role_profiles,
                ledger.calls,
                len(attempts),
                final_exact,
                tuple(attempts),
                'verified_causal_probe',
            )
        if len(attempts) >= budget.max_interventions:
            break

    return _failure_receipt('no_verified_causal_probe', ledger, attempts)

__all__ = [
    'ExposureSchema', 'ProbeBudget', 'ProbeAttemptReceipt', 'ActiveProbeReceipt',
    'discover_exposure_schemas', 'discover_verified_subgoal',
]
