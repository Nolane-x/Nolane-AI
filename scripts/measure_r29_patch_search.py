from __future__ import annotations

import json
from pathlib import Path

from benchmarks.codeworld.r29_patch_cases import locked_r29_cases
from cogcoder.r29_patch_model import patch_fingerprint
from cogcoder.r29_patch_search import VerifierGuidedPatchSearch


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / 'research' / 'R2_9_PRE_DEV_LOCK.json'
PARENT_RESULT_PATH = ROOT / 'research' / 'R2_8_PHASE_A_RESULT.json'


def _run(case):
    return VerifierGuidedPatchSearch(budget=case.budget).search(
        case.snapshot,
        case.initial_candidates,
        case.evaluator,
        refine=case.refine,
        graph=case.graph,
    )


def measure_r29_patch_search() -> dict[str, object]:
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    parent = json.loads(PARENT_RESULT_PATH.read_text(encoding='utf-8'))
    original_cases = locked_r29_cases(id_prefix='measure-a-')
    renamed_cases = locked_r29_cases(id_prefix='measure-b-')

    rows: list[dict[str, object]] = []
    verified_solves = 0
    false_terminal_accepts = 0
    duplicate_evaluator_calls = 0
    rename_invariant_cases = 0
    max_evaluator_calls = 0

    for case, renamed in zip(original_cases, renamed_cases):
        outcome = _run(case)
        renamed_outcome = _run(renamed)
        verified_solves += int(outcome.success and outcome.best_result.success)
        false_terminal_accepts += int(outcome.success and not outcome.best_result.success)
        repeated = outcome.evaluations - len({step.fingerprint for step in outcome.trace})
        duplicate_evaluator_calls += repeated
        invariant = [step.fingerprint for step in outcome.trace] == [
            step.fingerprint for step in renamed_outcome.trace
        ]
        rename_invariant_cases += int(invariant)
        max_evaluator_calls = max(max_evaluator_calls, outcome.evaluations)
        rows.append(
            {
                'case': case.name,
                'language': case.language,
                'success': outcome.success,
                'evaluations': outcome.evaluations,
                'duplicate_candidates_filtered': outcome.duplicate_candidates,
                'trace_fingerprints': [step.fingerprint for step in outcome.trace],
                'rename_invariant': invariant,
                'selected_fingerprint': patch_fingerprint(outcome.candidate) if outcome.candidate else None,
                'expected_fingerprint': case.expected_patch_fingerprint,
            }
        )

    new_parameters = 0
    candidate_parameters = int(parent['candidate_effective_parameters']) + new_parameters
    acceptance = lock['acceptance']
    phase_a_gate_pass = all(
        (
            verified_solves >= int(acceptance['verified_solves_min']),
            false_terminal_accepts <= int(acceptance['false_terminal_accepts_max']),
            duplicate_evaluator_calls <= int(acceptance['duplicate_evaluator_calls_max']),
            rename_invariant_cases >= int(acceptance['rename_invariant_cases_min']),
            max_evaluator_calls <= int(acceptance['max_evaluator_calls_observed_max']),
            new_parameters <= int(acceptance['new_neural_parameters_max']),
            candidate_parameters <= int(lock['candidate_parameter_ceiling']),
        )
    )
    return {
        'milestone': 'R2.9 Verifier-Guided Patch Search',
        'phase': 'A',
        'cases': len(original_cases),
        'verified_solves': verified_solves,
        'false_terminal_accepts': false_terminal_accepts,
        'duplicate_evaluator_calls': duplicate_evaluator_calls,
        'rename_invariant_cases': rename_invariant_cases,
        'max_evaluator_calls_observed': max_evaluator_calls,
        'parent_effective_parameters': int(parent['candidate_effective_parameters']),
        'new_r29_neural_parameters': new_parameters,
        'candidate_effective_parameters': candidate_parameters,
        'external_coding_claim_allowed': False,
        'agi_claim_allowed': False,
        'phase_a_gate_pass': phase_a_gate_pass,
        'claim_boundary': lock['claim_boundary'],
        'rows': rows,
    }


def main() -> None:
    print(json.dumps(measure_r29_patch_search(), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
