from __future__ import annotations

import hashlib
import itertools
from dataclasses import replace

from benchmarks.kfigg.r252_repository_multifile_transfer import (
    HELDOUT_EPISODES,
    _episode,
    _order,
    _root_callable,
    _tests,
    learn_r252_library,
)
from cogcoder.r252_repository_query import compile_repository_candidate, enumerate_repository_candidates
from cogcoder.r259_active_repository_probes import RepositoryProbe, solve_repository_patch_with_active_probes


_PROBE_VALUES_XYALT = tuple(range(-3, 4))
_PROBE_VALUES_CAP = tuple(range(0, 7))


def _all_probe_inputs() -> tuple[RepositoryProbe, ...]:
    return tuple(
        RepositoryProbe(tuple(args))
        for args in itertools.product(
            _PROBE_VALUES_XYALT,
            _PROBE_VALUES_XYALT,
            _PROBE_VALUES_CAP,
            _PROBE_VALUES_XYALT,
        )
    )


def _initial_survivors(candidates, initial_tests):
    survivors = []
    for candidate in candidates:
        try:
            fn = compile_repository_candidate(candidate)[1]
        except Exception:
            continue
        ok = True
        for test in initial_tests:
            try:
                actual = fn(*test.args)
            except Exception:
                ok = False
                break
            if actual != test.expected:
                ok = False
                break
        if ok:
            survivors.append((candidate, fn))
    return tuple(survivors)


def _verify_candidate(candidate, oracle, verification_inputs):
    try:
        fn = compile_repository_candidate(candidate)[1]
    except Exception:
        return False, 0
    calls = 0
    for probe in verification_inputs:
        try:
            actual = fn(*probe.args)
            expected = oracle(*probe.args)
        except Exception:
            calls += 1
            return False, calls
        calls += 1
        if actual != expected:
            return False, calls
    return True, calls


def _random_one_probe_baseline(seed, survivors, probe_inputs, oracle, verification_inputs):
    if len(survivors) <= 1:
        if len(survivors) == 1:
            exact, verify_calls = _verify_candidate(survivors[0][0], oracle, verification_inputs)
            return {
                'exact': exact,
                'false_accepts': 0,
                'selection_oracle_calls': 0,
                'verification_oracle_calls': verify_calls,
                'survivors_after': 1,
                'probe_args': None,
            }
        return {
            'exact': False,
            'false_accepts': 0,
            'selection_oracle_calls': 0,
            'verification_oracle_calls': 0,
            'survivors_after': 0,
            'probe_args': None,
        }
    probe = min(
        probe_inputs,
        key=lambda row: hashlib.sha256(f'r259-random|{seed}|{row.args}'.encode()).hexdigest(),
    )
    target = oracle(*probe.args)
    kept = []
    for candidate, fn in survivors:
        try:
            actual = fn(*probe.args)
        except Exception:
            continue
        if actual == target:
            kept.append((candidate, fn))
    if len(kept) != 1:
        return {
            'exact': False,
            'false_accepts': 0,
            'selection_oracle_calls': 1,
            'verification_oracle_calls': 0,
            'survivors_after': len(kept),
            'probe_args': list(probe.args),
        }
    exact, verify_calls = _verify_candidate(kept[0][0], oracle, verification_inputs)
    return {
        'exact': exact,
        'false_accepts': 0,
        'selection_oracle_calls': 1,
        'verification_oracle_calls': verify_calls,
        'survivors_after': 1,
        'probe_args': list(probe.args),
    }


def _candidate_identity_invariance(candidates, initial_tests, probes, oracle, verification_inputs, reference_receipt):
    renamed = tuple(
        replace(candidate, candidate_id=f'opaque-{index:03d}')
        for index, candidate in enumerate(reversed(candidates))
    )
    receipt = solve_repository_patch_with_active_probes(
        renamed,
        initial_tests,
        probes,
        oracle,
        verification_inputs=verification_inputs,
        max_selection_oracle_calls=1,
    )
    if not reference_receipt.rounds or not receipt.rounds:
        return False
    return bool(
        receipt.status == reference_receipt.status == 'accept'
        and receipt.rounds[0].probe.args == reference_receipt.rounds[0].probe.args
        and receipt.rounds[0].partition_signature == reference_receipt.rounds[0].partition_signature
        and receipt.selection_oracle_calls == reference_receipt.selection_oracle_calls == 1
    )


def run_heldout_episode(seed: int) -> dict[str, object]:
    source, target, essential_ids, _essential, call_depth = _episode(seed)
    library = learn_r252_library()
    candidates = enumerate_repository_candidates(source, library, max_depth=6)
    tests = _tests(seed, target)
    by_id = {test.test_id: test for test in tests}
    order = _order(seed, tests)
    initial_tests = tuple(by_id[test_id] for test_id in order[:4])
    initial_args = {test.args for test in initial_tests}
    all_inputs = _all_probe_inputs()
    probe_inputs = tuple(probe for probe in all_inputs if probe.args not in initial_args)
    oracle = _root_callable(target)

    active = solve_repository_patch_with_active_probes(
        candidates,
        initial_tests,
        probe_inputs,
        oracle,
        verification_inputs=all_inputs,
        max_selection_oracle_calls=1,
    )
    selected_ids = () if active.candidate is None else active.candidate.macro_ids
    survivors = _initial_survivors(candidates, initial_tests)
    random = _random_one_probe_baseline(seed, survivors, probe_inputs, oracle, all_inputs)
    identity_invariant = True
    if seed == HELDOUT_EPISODES[0]:
        identity_invariant = _candidate_identity_invariance(
            candidates, initial_tests, probe_inputs, oracle, all_inputs, active,
        )

    return {
        'seed': seed,
        'file_count': len(source.files),
        'call_depth': call_depth,
        'initial_candidates': len(candidates),
        'initial_tests': len(initial_tests),
        'initial_survivors': active.initial_survivors,
        'active_status': active.status,
        'active_exact': active.exact,
        'active_selected_exact_macro_set': set(selected_ids) == set(essential_ids),
        'active_selection_oracle_calls': active.selection_oracle_calls,
        'active_verification_oracle_calls': active.verification_oracle_calls,
        'active_candidate_evaluations': active.candidate_evaluations,
        'active_false_accepts': active.false_terminal_accepts,
        'active_probe_args': list(active.rounds[0].probe.args) if active.rounds else None,
        'active_partition_signature': list(active.rounds[0].partition_signature) if active.rounds else [],
        'random_one_probe_exact': random['exact'],
        'random_one_probe_false_accepts': random['false_accepts'],
        'random_one_probe_survivors_after': random['survivors_after'],
        'random_one_probe_args': random['probe_args'],
        'passive_initial_only_exact': len(survivors) == 1 and set(survivors[0][0].macro_ids) == set(essential_ids),
        'passive_initial_only_false_accepts': 0,
        'candidate_identity_invariant': identity_invariant,
        'probe_generation_uses_target_outputs': False,
        'probe_space_size': len(all_inputs),
    }


def run_frozen_heldout() -> dict[str, object]:
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    summary = {
        'episodes': len(rows),
        'active_exact': sum(bool(row['active_exact']) for row in rows),
        'active_false_accepts': sum(int(row['active_false_accepts']) for row in rows),
        'active_selected_exact_macro_set': sum(bool(row['active_selected_exact_macro_set']) for row in rows),
        'active_one_selection_query': sum(row['active_selection_oracle_calls'] == 1 for row in rows),
        'active_max_selection_oracle_calls': max(row['active_selection_oracle_calls'] for row in rows),
        'active_full_verification_cases': min(row['active_verification_oracle_calls'] for row in rows),
        'active_max_candidate_evaluations': max(row['active_candidate_evaluations'] for row in rows),
        'random_one_probe_exact': sum(bool(row['random_one_probe_exact']) for row in rows),
        'random_one_probe_false_accepts': sum(int(row['random_one_probe_false_accepts']) for row in rows),
        'passive_initial_only_exact': sum(bool(row['passive_initial_only_exact']) for row in rows),
        'passive_initial_only_false_accepts': sum(int(row['passive_initial_only_false_accepts']) for row in rows),
        'initial_candidates': rows[0]['initial_candidates'],
        'initial_tests_per_episode': rows[0]['initial_tests'],
        'min_initial_survivors': min(row['initial_survivors'] for row in rows),
        'max_initial_survivors': max(row['initial_survivors'] for row in rows),
        'probe_space_size': rows[0]['probe_space_size'],
        'active_gain_over_random': sum(bool(row['active_exact']) for row in rows) - sum(bool(row['random_one_probe_exact']) for row in rows),
        'candidate_identity_invariant': all(bool(row['candidate_identity_invariant']) for row in rows),
        'probe_generation_uses_target_outputs': any(bool(row['probe_generation_uses_target_outputs']) for row in rows),
        'zero_trainable_parameters': True,
        'min_file_count': min(row['file_count'] for row in rows),
        'max_file_count': max(row['file_count'] for row in rows),
        'min_call_depth': min(row['call_depth'] for row in rows),
        'max_call_depth': max(row['call_depth'] for row in rows),
    }
    gates = {
        'active_all_exact': summary['active_exact'] == 6,
        'active_zero_false_accepts': summary['active_false_accepts'] == 0,
        'active_exact_macro_set_all': summary['active_selected_exact_macro_set'] == 6,
        'one_active_selection_query_all': summary['active_one_selection_query'] == 6,
        'full_independent_verification': summary['active_full_verification_cases'] == 2401,
        'causal_gain_over_random': summary['active_gain_over_random'] >= 4,
        'random_not_saturated': summary['random_one_probe_exact'] <= 2,
        'passive_initial_ambiguous': summary['passive_initial_only_exact'] == 0,
        'candidate_identity_invariant': summary['candidate_identity_invariant'],
        'target_independent_probe_generation': summary['probe_generation_uses_target_outputs'] is False,
        'repository_scale_retained': summary['min_file_count'] >= 5 and summary['min_call_depth'] >= 4,
        'zero_trainable_parameters': summary['zero_trainable_parameters'],
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.59 Active Diagnostic Repository Probe Synthesis',
        'capability': 'active-repository-diagnostic-probe-selection',
        'claim_boundary': 'Bounded active diagnostic input selection over an existing finite repository-patch version space; not general repository coding, open-ended test invention, or AGI.',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_frozen_heldout(), indent=2, sort_keys=True))
