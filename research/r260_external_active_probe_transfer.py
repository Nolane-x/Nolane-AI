from __future__ import annotations

from typing import Callable

from cogcoder.r247_executable_patch_cegis import PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate, compile_repository_candidate
from cogcoder.r260_active_repository_probes import (
    RepositoryProbe,
    enumerate_probe_inputs,
    solve_repository_patch_with_active_probes,
)


def _candidate(candidate_id: str, source: str) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id=candidate_id, macro_ids=(f'behavior:{candidate_id}',), files=(('candidate.py', source),), support_score=1, edit_count=1)


def _candidates() -> tuple[RepositoryPatchCandidate, ...]:
    return (
        _candidate('euclidean-gcd', 'def solve(a, b):\n    a = abs(a)\n    b = abs(b)\n    while b != 0:\n        a, b = b, a % b\n    return a\n'),
        _candidate('absolute-difference', 'def solve(a, b):\n    return abs(a - b)\n'),
        _candidate('half-minimum-magnitude', 'def solve(a, b):\n    aa = abs(a)\n    bb = abs(b)\n    return (aa if aa < bb else bb) // 2\n'),
        _candidate('third-maximum-magnitude', 'def solve(a, b):\n    return max(abs(a), abs(b)) // 3\n'),
    )


def _initial_tests(oracle: Callable[[int, int], object]) -> tuple[PatchTest, ...]:
    cases = ((6, 9), (8, 12))
    return tuple(PatchTest(f'initial-{index}', args, oracle(*args)) for index, args in enumerate(cases))


def _initial_survivors(candidates: tuple[RepositoryPatchCandidate, ...], tests: tuple[PatchTest, ...]) -> tuple[tuple[RepositoryPatchCandidate, Callable[..., object]], ...]:
    survivors = []
    for candidate in candidates:
        try:
            _root, fn = compile_repository_candidate(candidate)
        except Exception:
            continue
        if all(fn(*test.args) == test.expected for test in tests):
            survivors.append((candidate, fn))
    return tuple(survivors)


def _target_independent_one_probe_baseline(survivors: tuple[tuple[RepositoryPatchCandidate, Callable[..., object]], ...], probes: tuple[RepositoryProbe, ...], oracle: Callable[[int, int], object]) -> dict[str, object]:
    probe = min(probes, key=lambda row: row.probe_id)
    target = oracle(*probe.args)
    kept = []
    for candidate, fn in survivors:
        try:
            if fn(*probe.args) == target:
                kept.append(candidate)
        except Exception:
            continue
    return {'exact': len(kept) == 1 and kept[0].candidate_id == 'euclidean-gcd', 'survivors_after': len(kept), 'probe_args': list(probe.args), 'selection_oracle_calls': 1}


def run_external_transfer(oracle: Callable[[int, int], object], *, source_id: str, source_version: str) -> dict[str, object]:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    source_id = str(source_id).strip(); source_version = str(source_version).strip()
    if not source_id or not source_version:
        raise ValueError('source_id and source_version must be non-empty')
    candidates = _candidates()
    initial_tests = _initial_tests(oracle)
    initial_oracle_calls = len(initial_tests)
    survivors = _initial_survivors(candidates, initial_tests)
    if len(survivors) != len(candidates):
        raise AssertionError('external transfer initial evidence must preserve all four hypotheses')
    probes = enumerate_probe_inputs(2, range(-12, 13))
    random_baseline = _target_independent_one_probe_baseline(survivors, probes, oracle)
    active = solve_repository_patch_with_active_probes(candidates, initial_tests, probes, oracle, verification_inputs=probes, max_selection_oracle_calls=1)
    selected_is_correct = bool(active.candidate is not None and active.candidate.candidate_id == 'euclidean-gcd')
    active_exact = bool(active.status == 'accept' and active.exact and selected_is_correct)
    selected_partition_count = active.rounds[0].partition_count if active.rounds else 0
    selected_largest_partition = active.rounds[0].largest_partition if active.rounds else 0
    random_exact = bool(random_baseline['exact'])
    verification_exact = len(probes) if active_exact and active.verification_failures == 0 else 0
    oracle_calls_total = initial_oracle_calls + int(random_baseline['selection_oracle_calls']) + active.oracle_calls_total
    passed = bool(active_exact and active.false_terminal_accepts == 0 and active.selection_oracle_calls == 1 and selected_partition_count == 4 and selected_largest_partition == 1 and verification_exact == len(probes) == 625 and not random_exact and len(survivors) > 1)
    return {
        'passed': passed,
        'milestone': 'R2.60',
        'capability': 'external-active-diagnostic-probe-transfer',
        'source_id': source_id,
        'source_version': source_version,
        'source_exposure': 'io_only',
        'candidate_count': len(candidates),
        'initial_oracle_calls': initial_oracle_calls,
        'initial_survivors': len(survivors),
        'active_selection_oracle_calls': active.selection_oracle_calls,
        'active_verification_oracle_calls': active.verification_oracle_calls,
        'active_exact': active_exact,
        'active_false_accepts': active.false_terminal_accepts,
        'selected_probe_args': list(active.rounds[0].probe.args) if active.rounds else None,
        'selected_probe_partition_count': selected_partition_count,
        'selected_probe_largest_partition': selected_largest_partition,
        'random_one_probe_exact': random_exact,
        'random_one_probe_args': random_baseline['probe_args'],
        'random_one_probe_survivors_after': random_baseline['survivors_after'],
        'passive_initial_only_exact': len(survivors) == 1,
        'active_gain_over_random': active_exact and not random_exact,
        'verification_cases': len(probes),
        'verification_exact': verification_exact,
        'oracle_calls_total': oracle_calls_total,
        'probe_generation_uses_target_outputs': False,
        'trainable_parameter_count': 0,
        'claim_boundary': 'I/O-only transfer to one independently sourced integer ufunc over a host-authored finite four-hypothesis behavior set; not general repository coding, open-ended test invention, unrestricted program synthesis, or AGI.',
    }


__all__ = ['run_external_transfer']
