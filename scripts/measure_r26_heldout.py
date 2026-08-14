from __future__ import annotations

import argparse
import json
from pathlib import Path

from cogcoder.arc_eval import load_task
from cogcoder.r26_candidate import program_set
from cogcoder.r26_score import score_with_candidates
from cogcoder.r26_split import partition_paths

ARC_REVISION = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'
CANDIDATE_RUNTIME_COMMIT = '059ba04f134954880e19c1e6ec89d2ff5d0cdc1d'
CANDIDATE_LOCK_COMMIT = 'e51bcbed97ec0d90cd5264b38f72a2fc9229b1a5'


def measure(directory: str | Path, *, max_attempts: int = 2, max_programs: int = 64) -> dict:
    if max_attempts != 2:
        raise ValueError('R2.6 heldout protocol is locked to exactly two attempts')
    if max_programs != 64:
        raise ValueError('R2.6 heldout protocol is locked to exactly 64 programs')

    # Partitioning reads filenames only. DEVELOPMENT paths are discarded before
    # any task JSON is parsed, so this process scores INTERNAL_HELDOUT only.
    all_paths = tuple(sorted(Path(directory).glob('*.json'), key=lambda p: p.name))
    development, heldout = partition_paths(all_paths)
    development_count = len(development)
    del development

    solved = errors = candidates_total = attempts_total = 0
    for path in heldout:
        try:
            task = load_task(path)
            candidates = program_set(task.train_pairs, limit=max_programs)
            result = score_with_candidates(
                task,
                candidates,
                max_attempts=max_attempts,
                max_programs=max_programs,
            )
        except Exception:
            errors += 1
            continue
        solved += int(result.solved)
        candidates_total += result.candidate_programs
        attempts_total += result.attempts_emitted

    cases = len(heldout)
    scored = max(0, cases - errors)
    return {
        'aggregate_only': True,
        'arc_revision': ARC_REVISION,
        'candidate_runtime_commit': CANDIDATE_RUNTIME_COMMIT,
        'candidate_lock_commit': CANDIDATE_LOCK_COMMIT,
        'partition': 'internal_heldout',
        'development_paths_not_loaded': True,
        'development_case_count_from_filenames_only': development_count,
        'cases': cases,
        'scored': scored,
        'solved': solved,
        'solve_rate': solved / max(1, cases),
        'errors': errors,
        'mean_candidate_programs': candidates_total / max(1, scored),
        'mean_attempts_emitted': attempts_total / max(1, scored),
        'max_attempts': max_attempts,
        'max_programs': max_programs,
        'gate_min_solved': 23,
        'gate_pass': solved >= 23 and errors == 0 and cases == 199,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--max-attempts', type=int, default=2)
    p.add_argument('--max-programs', type=int, default=64)
    args = p.parse_args()
    print(json.dumps(measure(
        args.directory,
        max_attempts=args.max_attempts,
        max_programs=args.max_programs,
    ), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
