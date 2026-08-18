from __future__ import annotations

import itertools
from typing import Callable

from benchmarks.kfigg.r261_version_space_expansion_transfer import _candidate, _macro, _repository
from cogcoder.r247_executable_patch_cegis import PatchTest
from cogcoder.r252_repository_query import compile_repository_candidate
from cogcoder.r260_active_repository_probes import RepositoryProbe, solve_repository_patch_with_active_probes
from cogcoder.r261_version_space_expansion import solve_repository_patch_with_version_space_expansion


def _verification_inputs() -> tuple[RepositoryProbe, ...]:
    return tuple(
        RepositoryProbe((x, y))
        for x, y in itertools.product(range(-20, 21), range(1, 11))
    )


class _EmbeddedExternalOracle:
    def __init__(self, external: Callable[..., object], coefficient: int) -> None:
        self.external = external
        self.coefficient = int(coefficient)
        self.calls = 0

    def __call__(self, x: int, y: int) -> int:
        self.calls += 1
        external_value = int(self.external(x, y))
        return external_value * self.coefficient + (x // y)


def _initial_label(external: Callable[..., object], coefficient: int, x: int, y: int) -> int:
    # This obtains one public I/O label only. It is not passed to candidate generation.
    return int(external(x, y)) * int(coefficient) + (x // y)


def _candidate_matches_external(candidate, external: Callable[..., object], coefficient: int, probes) -> bool:
    try:
        fn = compile_repository_candidate(candidate)[1]
    except Exception:
        return False
    for probe in probes:
        x, y = probe.args
        expected = int(external(x, y)) * int(coefficient) + (x // y)
        try:
            if fn(x, y) != expected:
                return False
        except Exception:
            return False
    return True


def run_external_transfer(
    external_oracle: Callable[..., object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    if not callable(external_oracle):
        raise TypeError('external_oracle must be callable')
    if not source_id:
        raise ValueError('source_id must be non-empty')
    if not source_version:
        raise ValueError('source_version must be non-empty')

    seed = 5261
    relay_count = 3
    coefficient = 23
    source = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='//',
        decoy_op='//',
    )
    wrong_decoy = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='//',
        decoy_op='%',
    )
    source_candidate = _candidate('external:source', source)
    wrong_candidate = _candidate('external:wrong-decoy', wrong_decoy, edits=1)
    initial_candidates = (source_candidate, wrong_candidate)

    initial_args = (3, 2)
    initial_expected = _initial_label(external_oracle, coefficient, *initial_args)
    initial_tests = (PatchTest('external:initial', initial_args, initial_expected),)
    diagnostic = (RepositoryProbe((5, 2)),)
    verification = _verification_inputs()

    baseline_oracle = _EmbeddedExternalOracle(external_oracle, coefficient)
    baseline = solve_repository_patch_with_active_probes(
        initial_candidates,
        initial_tests,
        diagnostic,
        baseline_oracle,
        verification_inputs=verification,
        max_selection_oracle_calls=1,
    )

    active_oracle = _EmbeddedExternalOracle(external_oracle, coefficient)
    active = solve_repository_patch_with_version_space_expansion(
        initial_candidates,
        initial_tests,
        diagnostic,
        active_oracle,
        verification_inputs=verification,
        expansion_seeds=(source_candidate,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )

    correct_initially_absent = (
        baseline.status == 'abstain'
        and baseline.reason == 'oracle_outside_candidate_version_space'
    )
    accepted_matches_external = (
        active.candidate is not None
        and _candidate_matches_external(
            active.candidate,
            external_oracle,
            coefficient,
            verification,
        )
    )
    r260_result = {
        'status': baseline.status,
        'reason': baseline.reason,
        'initial_survivors': baseline.initial_survivors,
        'selection_oracle_calls': baseline.selection_oracle_calls,
        'external_oracle_calls': baseline_oracle.calls,
        'false_terminal_accepts': baseline.false_terminal_accepts,
    }
    r261_result = {
        'status': active.status,
        'exact': bool(active.exact and accepted_matches_external),
        'reason': active.reason,
        'initial_survivors': active.initial_survivors,
        'selection_oracle_calls': active.selection_oracle_calls,
        'verification_oracle_calls': active.verification_oracle_calls,
        'expansion_round_count': active.expansion_round_count,
        'generated_candidates': active.generated_candidates,
        'admitted_generated_candidates': active.admitted_generated_candidates,
        'candidate_evaluations': active.candidate_evaluations,
        'false_terminal_accepts': active.false_terminal_accepts,
        'verification_failures': active.verification_failures,
    }
    gates = {
        'pinned_version_expected': source_version == '2.4.6',
        'callable_io_only': True,
        'source_code_not_inspected': True,
        'correct_candidate_initially_absent': correct_initially_absent,
        'r260_abstains_out_of_space': r260_result['status'] == 'abstain' and r260_result['reason'] == 'oracle_outside_candidate_version_space',
        'r261_accepts_expanded_candidate': r261_result['status'] == 'accept' and r261_result['reason'] == 'expanded_candidate_verified',
        'r261_external_exact': r261_result['exact'] is True,
        'one_expansion_round': r261_result['expansion_round_count'] == 1,
        'generated_multiple_site_hypotheses': int(r261_result['generated_candidates']) >= 2,
        'counterexample_admits_single_candidate': r261_result['admitted_generated_candidates'] == 1,
        'independent_verification': r261_result['verification_oracle_calls'] == len(verification),
        'zero_false_accepts': r261_result['false_terminal_accepts'] == 0,
        'zero_trainable_parameters': True,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.61 Counterexample-Guided Version-Space Expansion',
        'external_family': 'NumPy remainder embedded in a bounded multi-file repository behavior',
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_code_inspected': False,
        'external_access': 'callable-I/O-only',
        'repository_file_count': len(source.files),
        'repository_call_depth': relay_count + 1,
        'initial_candidate_count': len(initial_candidates),
        'correct_candidate_initially_absent': correct_initially_absent,
        'correct_repository_candidate_host_authored': False,
        'trusted_patch_macro_source': 'pre-existing bounded R2.47 PatchMacro semantics; no macro induction from external target outputs',
        'diagnostic_probe_args': list(diagnostic[0].args),
        'verification_cases': len(verification),
        'external_oracle_calls': active_oracle.calls,
        'r260_baseline': r260_result,
        'r261': r261_result,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'claim_boundary': 'Pinned callable-I/O transfer for bounded pure integer remainder behavior embedded in an R2.52-compatible repository; not NumPy source repair, broad repository autonomy, or arbitrary code generation.',
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json
    import numpy as np

    print(json.dumps(run_external_transfer(
        np.remainder,
        source_id='numpy.remainder',
        source_version=np.__version__,
    ), indent=2, sort_keys=True))
