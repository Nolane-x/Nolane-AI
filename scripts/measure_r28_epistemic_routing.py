from __future__ import annotations

import json
from pathlib import Path

from benchmarks.codeworld.r28_epistemic_cases import build_cases, evaluate_cases


LOCK_PATH = Path('research/R2_8_PRE_DEV_LOCK.json')
RESULT_PATH = Path('research/R2_8_PHASE_A_RESULT.json')


def measure() -> dict[str, object]:
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    if int(lock['new_r28_neural_parameters']) != 0:
        raise RuntimeError('R2.8 Phase A is locked to zero new neural parameters')
    if int(lock['candidate_effective_parameters']) != int(lock['parent_effective_parameters']):
        raise RuntimeError('R2.8 Phase A candidate parameter count must equal its parent')

    result = evaluate_cases(build_cases())
    exact = float(result['exact_action_accuracy'])
    invariant = float(result['rename_invariance'])
    accepted = (
        exact >= float(lock['acceptance']['minimum_exact_action_accuracy'])
        and invariant >= float(lock['acceptance']['minimum_rename_invariance'])
    )
    payload: dict[str, object] = {
        'milestone': lock['milestone'],
        'phase': lock['phase'],
        'parent_source_commit': lock['parent_source_commit'],
        'parent_effective_parameters': lock['parent_effective_parameters'],
        'new_r28_neural_parameters': lock['new_r28_neural_parameters'],
        'candidate_effective_parameters': lock['candidate_effective_parameters'],
        'cases': result['cases'],
        'exact_action_accuracy': exact,
        'rename_invariance': invariant,
        'rows': result['rows'],
        'phase_a_gate_pass': accepted,
        'external_coding_claim_allowed': False,
        'claim_boundary': (
            'Internal architecture/cognition gate only. This result does not establish real-repository '
            'issue resolution, arbitrary patch generation, AGI, or frontier-model parity.'
        ),
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return payload


if __name__ == '__main__':
    measured = measure()
    print(json.dumps(measured, indent=2, sort_keys=True))
    if not measured['phase_a_gate_pass']:
        raise SystemExit(1)
