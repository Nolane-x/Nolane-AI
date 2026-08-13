from __future__ import annotations

import argparse
import json
from pathlib import Path

from cogcoder.arc_score_current import score_current
from cogcoder.arc_eval import load_task


def measure(directory: str | Path, *, max_attempts: int = 2, max_programs: int = 64) -> dict:
    root = Path(directory)
    paths = sorted(root.glob('*.json'))
    solved = errors = 0
    total_candidates = total_attempts = 0
    for path in paths:
        try:
            score = score_current(load_task(path), max_attempts=max_attempts, max_programs=max_programs)
        except Exception:
            errors += 1
            continue
        solved += int(score.solved)
        total_candidates += score.candidate_programs
        total_attempts += score.attempts_emitted
    cases = len(paths)
    scored = max(0, cases - errors)
    return {
        'cases': cases,
        'scored': scored,
        'solved': solved,
        'solve_rate': solved / max(1, cases),
        'errors': errors,
        'mean_candidate_programs': total_candidates / max(1, scored),
        'mean_attempts_emitted': total_attempts / max(1, scored),
        'max_attempts': int(max_attempts),
        'max_programs': int(max_programs),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--max-attempts', type=int, default=2)
    p.add_argument('--max-programs', type=int, default=64)
    a = p.parse_args()
    print(json.dumps(measure(a.directory, max_attempts=a.max_attempts, max_programs=a.max_programs), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
