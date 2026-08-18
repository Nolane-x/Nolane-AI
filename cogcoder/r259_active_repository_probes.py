from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from cogcoder.r247_executable_patch_cegis import PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate, compile_repository_candidate


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('probe values must be finite')
        return value
    raise TypeError('probe values must be JSON scalar values')


def _scalar_key(value: object) -> str:
    return json.dumps(_json_scalar(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class RepositoryProbe:
    args: tuple[object, ...]

    def __post_init__(self) -> None:
        args = tuple(_json_scalar(value) for value in tuple(self.args))
        if not args:
            raise ValueError('probe args must be non-empty')
        object.__setattr__(self, 'args', args)

    @property
    def probe_id(self) -> str:
        payload = json.dumps(list(self.args), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        return 'rprobe:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()


def enumerate_probe_inputs(arity: int, values: Iterable[object]) -> tuple[RepositoryProbe, ...]:
    arity = int(arity)
    if arity < 1:
        raise ValueError('arity must be positive')
    dedup: dict[str, object] = {}
    for value in values:
        normalized = _json_scalar(value)
        dedup.setdefault(_scalar_key(normalized), normalized)
    if not dedup:
        raise ValueError('values must be non-empty')
    ordered_values = tuple(dedup[key] for key in sorted(dedup))
    probes = [RepositoryProbe(tuple(args)) for args in itertools.product(ordered_values, repeat=arity)]
    return tuple(sorted(probes, key=lambda probe: probe.probe_id))


@dataclass(frozen=True, slots=True)
class ActiveProbeRound:
    round_index: int
    probe: RepositoryProbe
    survivors_before: int
    survivors_after: int
    partition_count: int
    largest_partition: int
    partition_signature: tuple[int, ...]
    oracle_outcome_key: str


@dataclass(frozen=True, slots=True)
class ActiveRepositoryProbeReceipt:
    status: str
    candidate: RepositoryPatchCandidate | None
    exact: bool
    initial_survivors: int
    final_survivors: int
    selection_oracle_calls: int
    verification_oracle_calls: int
    oracle_calls_total: int
    candidate_evaluations: int
    rounds: tuple[ActiveProbeRound, ...]
    false_terminal_accepts: int
    verification_failures: int
    reason: str
    trainable_parameter_count: int = 0


@dataclass(frozen=True, slots=True)
class _CompiledCandidate:
    candidate: RepositoryPatchCandidate
    fn: Callable[..., object]
    behavior_digest: str


def _candidate_behavior_digest(candidate: RepositoryPatchCandidate) -> str:
    payload = json.dumps(
        [[path, source] for path, source in candidate.files],
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _outcome(fn: Callable[..., object], args: Sequence[object]) -> tuple[str, object | None]:
    try:
        value = fn(*args)
    except Exception as exc:
        return f'error:{type(exc).__module__}.{type(exc).__qualname__}', None
    try:
        key = 'value:' + json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        key = f'value-repr:{type(value).__module__}.{type(value).__qualname__}:{repr(value)}'
    return key, value


def _oracle_outcome(oracle: Callable[..., object], args: Sequence[object]) -> tuple[str, object | None, bool]:
    try:
        value = oracle(*args)
    except Exception as exc:
        return f'error:{type(exc).__module__}.{type(exc).__qualname__}', None, False
    try:
        key = 'value:' + json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        key = f'value-repr:{type(value).__module__}.{type(value).__qualname__}:{repr(value)}'
    return key, value, True


def _compile_candidates(candidates: Sequence[RepositoryPatchCandidate]) -> tuple[tuple[_CompiledCandidate, ...], int]:
    compiled: list[_CompiledCandidate] = []
    evaluations = 0
    for candidate in candidates:
        evaluations += 1
        try:
            _root, fn = compile_repository_candidate(candidate)
        except Exception:
            continue
        if not callable(fn):
            continue
        compiled.append(_CompiledCandidate(candidate, fn, _candidate_behavior_digest(candidate)))
    compiled.sort(key=lambda row: (row.behavior_digest, row.candidate.files))
    return tuple(compiled), evaluations


def _filter_initial(candidates: Sequence[_CompiledCandidate], tests: Sequence[PatchTest]) -> tuple[tuple[_CompiledCandidate, ...], int]:
    survivors: list[_CompiledCandidate] = []
    evaluations = 0
    for row in candidates:
        ok = True
        for test in tests:
            evaluations += 1
            key, value = _outcome(row.fn, test.args)
            if key.startswith('error:') or value != test.expected:
                ok = False
                break
        if ok:
            survivors.append(row)
    return tuple(survivors), evaluations


def _best_probe(survivors: Sequence[_CompiledCandidate], probes: Sequence[RepositoryProbe], used_probe_ids: set[str]) -> tuple[RepositoryProbe | None, dict[str, tuple[_CompiledCandidate, ...]] | None, int]:
    best_probe: RepositoryProbe | None = None
    best_partitions: dict[str, tuple[_CompiledCandidate, ...]] | None = None
    best_key: tuple[object, ...] | None = None
    evaluations = 0
    for probe in probes:
        if probe.probe_id in used_probe_ids:
            continue
        buckets: dict[str, list[_CompiledCandidate]] = {}
        for row in survivors:
            outcome_key, _value = _outcome(row.fn, probe.args)
            evaluations += 1
            buckets.setdefault(outcome_key, []).append(row)
        if len(buckets) <= 1:
            continue
        sizes = tuple(sorted(len(bucket) for bucket in buckets.values()))
        rank = (sizes[-1], sum(size * size for size in sizes), -len(sizes), probe.probe_id)
        if best_key is None or rank < best_key:
            best_key = rank
            best_probe = probe
            best_partitions = {key: tuple(values) for key, values in buckets.items()}
    return best_probe, best_partitions, evaluations


def solve_repository_patch_with_active_probes(
    candidates: Sequence[RepositoryPatchCandidate],
    initial_tests: Sequence[PatchTest],
    probe_inputs: Sequence[RepositoryProbe],
    oracle: Callable[..., object],
    *,
    verification_inputs: Sequence[RepositoryProbe],
    max_selection_oracle_calls: int = 8,
) -> ActiveRepositoryProbeReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    candidates = tuple(candidates)
    initial_tests = tuple(initial_tests)
    probes = tuple(probe_inputs)
    verification = tuple(verification_inputs)
    budget = int(max_selection_oracle_calls)
    if budget < 0:
        raise ValueError('max_selection_oracle_calls must be non-negative')
    if not candidates:
        return ActiveRepositoryProbeReceipt('abstain', None, False, 0, 0, 0, 0, 0, 0, (), 0, 0, 'no_candidates')
    if not probes:
        raise ValueError('probe_inputs must be non-empty')
    if not verification:
        raise ValueError('verification_inputs must be non-empty')
    arities = {len(probe.args) for probe in probes}
    verification_arities = {len(probe.args) for probe in verification}
    test_arities = {len(test.args) for test in initial_tests}
    if len(arities) != 1 or len(verification_arities) != 1:
        raise ValueError('probe arity must be consistent')
    if arities != verification_arities or (test_arities and test_arities != arities):
        raise ValueError('initial, selection, and verification inputs must share arity')

    compiled, candidate_evaluations = _compile_candidates(candidates)
    survivors, initial_evals = _filter_initial(compiled, initial_tests)
    candidate_evaluations += initial_evals
    initial_survivors = len(survivors)
    selection_calls = 0
    verification_calls = 0
    rounds: list[ActiveProbeRound] = []
    used_probe_ids: set[str] = set()

    if not survivors:
        return ActiveRepositoryProbeReceipt('abstain', None, False, 0, 0, 0, 0, 0, candidate_evaluations, (), 0, 0, 'repository_version_space_empty')

    while len(survivors) > 1:
        if selection_calls >= budget:
            return ActiveRepositoryProbeReceipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, verification_calls, selection_calls + verification_calls, candidate_evaluations, tuple(rounds), 0, 0, 'selection_oracle_budget_exhausted')
        probe, partitions, evals = _best_probe(survivors, probes, used_probe_ids)
        candidate_evaluations += evals
        if probe is None or partitions is None:
            return ActiveRepositoryProbeReceipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, verification_calls, selection_calls + verification_calls, candidate_evaluations, tuple(rounds), 0, 0, 'no_informative_probe')
        before = len(survivors)
        sizes = tuple(sorted(len(bucket) for bucket in partitions.values()))
        oracle_key, _oracle_value_result, oracle_ok = _oracle_outcome(oracle, probe.args)
        selection_calls += 1
        used_probe_ids.add(probe.probe_id)
        if not oracle_ok:
            return ActiveRepositoryProbeReceipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, verification_calls, selection_calls + verification_calls, candidate_evaluations, tuple(rounds), 0, 0, 'selection_oracle_error')
        survivors = partitions.get(oracle_key, ())
        rounds.append(ActiveProbeRound(len(rounds), probe, before, len(survivors), len(partitions), sizes[-1], sizes, oracle_key))
        if not survivors:
            return ActiveRepositoryProbeReceipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, selection_calls + verification_calls, candidate_evaluations, tuple(rounds), 0, 0, 'oracle_outside_candidate_version_space')

    selected = survivors[0]
    verification_failures = 0
    for probe in verification:
        candidate_key, _candidate_value = _outcome(selected.fn, probe.args)
        candidate_evaluations += 1
        oracle_key, _oracle_value_result, oracle_ok = _oracle_outcome(oracle, probe.args)
        verification_calls += 1
        if not oracle_ok or candidate_key != oracle_key:
            verification_failures += 1
            return ActiveRepositoryProbeReceipt('abstain', None, False, initial_survivors, 1, selection_calls, verification_calls, selection_calls + verification_calls, candidate_evaluations, tuple(rounds), 0, verification_failures, 'independent_verification_failed')

    return ActiveRepositoryProbeReceipt('accept', selected.candidate, True, initial_survivors, 1, selection_calls, verification_calls, selection_calls + verification_calls, candidate_evaluations, tuple(rounds), 0, 0, 'active_probe_verified')


__all__ = [
    'RepositoryProbe', 'ActiveProbeRound', 'ActiveRepositoryProbeReceipt',
    'enumerate_probe_inputs', 'solve_repository_patch_with_active_probes',
]
