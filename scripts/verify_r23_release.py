from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cogcoder.skill_curriculum import measure_kfigg23

ROOT = Path(__file__).resolve().parents[1]

LOCKED_BLOBS = {
    'cogcoder/continual_skills.py': '4e8ef528f91b6e03114499e8700d912014082120',
    'cogcoder/curriculum_cases.py': 'fe69bf92dfab4927c3b9da6861121384b665c156',
    'cogcoder/curriculum_eval.py': 'cb17f7486becb3a88050fd8b697d649442f86714',
    'cogcoder/skill_curriculum.py': '735f7d5f418df6c7f70ef97ebe12a0befec18118',
    'cogcoder/skill_memory.py': '87512a61c74c7c4e66785593a79fc13bdbf15dbd',
    'cogcoder/skill_synthesis.py': '941785bfa59aa753d44713f7c0f92f9c98829c3b',
    'scripts/evaluate_r23_continual.py': 'acaaa0ae74b9f84feef37fcc337dccb016e957da',
}

EXPECTED = {
    'cases': 200,
    'queries': 800,
    'baseline_solved': 270,
    'candidate_solved': 745,
    'baseline_solve_rate': 0.3375,
    'candidate_solve_rate': 0.93125,
    'gain_pp': 59.375,
    'induction_solve_rate': 0.94,
    'retention_solve_rate': 0.965,
    'revision_solve_rate': 0.925,
    'composition_solve_rate': 0.895,
    'integrity_failures': 0,
    'synthesis_failures': 0,
}


def verify_blob_identities() -> None:
    for relative, expected in LOCKED_BLOBS.items():
        path = ROOT / relative
        actual = subprocess.check_output(['git', 'hash-object', str(path)], cwd=ROOT, text=True).strip()
        if actual != expected:
            raise AssertionError(f'R2.3 locked source drift: {relative}: {actual} != {expected}')


def verify_final_heldout() -> dict:
    result = measure_kfigg23(
        seeds=range(8000, 8200),
        seen_probability=0.35,
        composition_seen_probability=0.25,
        max_depth=3,
        max_candidates=100000,
        demonstrations_per_skill=3,
    )
    for key, expected in EXPECTED.items():
        actual = result[key]
        if isinstance(expected, float):
            if abs(float(actual) - expected) > 1e-12:
                raise AssertionError(f'R2.3 heldout drift: {key}: {actual} != {expected}')
        elif actual != expected:
            raise AssertionError(f'R2.3 heldout drift: {key}: {actual} != {expected}')
    return {key: result[key] for key in EXPECTED}


def main() -> None:
    verify_blob_identities()
    heldout = verify_final_heldout()
    print(json.dumps({'status': 'PASS', 'heldout': heldout}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
