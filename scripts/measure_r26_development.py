from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cogcoder.arc_eval import load_task
from cogcoder.r26_candidate import program_set
from cogcoder.r26_score import score_with_candidates
from cogcoder.r26_split import partition_paths

ARC_REVISION = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'


def measure(directory: str | Path, *, max_attempts: int = 2, max_programs: int = 64) -> dict:
    if max_attempts != 2 or max_programs != 64:
        raise ValueError('R2.6 development protocol is locked to 2 attempts / 64 programs')
    all_paths = tuple(sorted(Path(directory).glob('*.json'), key=lambda p: p.name))
    development, heldout = partition_paths(all_paths)
    del heldout  # heldout paths are never loaded or passed to the scorer.

    solved = errors = candidates_total = attempts_total = 0
    robust_tasks = robust_candidates = 0
    family_counts: Counter[str] = Counter()
    for path in development:
        try:
            task = load_task(path)
            candidates = program_set(task.train_pairs, limit=max_programs)
            robust = [candidate for candidate in candidates if not candidate.legacy]
            robust_tasks += int(bool(robust))
            robust_candidates += len(robust)
            family_counts.update(candidate.family for candidate in robust)
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

    cases = len(development)
    scored = max(0, cases - errors)
    return {
        'arc_revision': ARC_REVISION,
        'partition': 'development',
        'cases': cases,
        'scored': scored,
        'solved': solved,
        'solve_rate': solved / max(1, cases),
        'errors': errors,
        'mean_candidate_programs': candidates_total / max(1, scored),
        'mean_attempts_emitted': attempts_total / max(1, scored),
        'robust_tasks': robust_tasks,
        'robust_candidates': robust_candidates,
        'robust_family_counts': dict(sorted(family_counts.items())),
        'max_attempts': max_attempts,
        'max_programs': max_programs,
        'internal_heldout_loaded': False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--max-attempts', type=int, default=2)
    p.add_argument('--max-programs', type=int, default=64)
    args = p.parse_args()
    print(json.dumps(measure(args.directory, max_attempts=args.max_attempts, max_programs=args.max_programs), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
