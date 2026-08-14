from __future__ import annotations

import argparse
import json
from pathlib import Path

from cogcoder import r25_n as base
from cogcoder.arc_candidate_region import program_set as frozen_program_set
from cogcoder.arc_eval import load_task
from cogcoder.r26_split import partition_paths

ARC_REVISION = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'


def _measure(paths: tuple[Path, ...], max_attempts: int, max_programs: int) -> dict:
    solved = errors = candidates = attempts = 0
    previous = base.program_set
    base.program_set = frozen_program_set
    try:
        for path in paths:
            try:
                result = base.score(load_task(path), max_attempts, max_programs)
            except Exception:
                errors += 1
                continue
            solved += int(result.solved)
            candidates += result.candidate_programs
            attempts += result.attempts_emitted
    finally:
        base.program_set = previous
    cases = len(paths)
    scored = max(0, cases - errors)
    return {
        'cases': cases,
        'scored': scored,
        'solved': solved,
        'solve_rate': solved / max(1, cases),
        'errors': errors,
        'mean_candidate_programs': candidates / max(1, scored),
        'mean_attempts_emitted': attempts / max(1, scored),
    }


def measure(directory: str | Path, max_attempts: int = 2, max_programs: int = 64) -> dict:
    if max_attempts != 2:
        raise ValueError('R2.6 baseline is locked to exactly two attempts')
    if max_programs != 64:
        raise ValueError('R2.6 baseline is locked to exactly 64 programs')
    paths = tuple(sorted(Path(directory).glob('*.json'), key=lambda p: p.name))
    development, heldout = partition_paths(paths)
    return {
        'arc_revision': ARC_REVISION,
        'max_attempts': max_attempts,
        'max_programs': max_programs,
        'development': _measure(development, max_attempts, max_programs),
        'internal_heldout': _measure(heldout, max_attempts, max_programs),
        'aggregate_only': True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--max-attempts', type=int, default=2)
    p.add_argument('--max-programs', type=int, default=64)
    args = p.parse_args()
    print(json.dumps(measure(args.directory, args.max_attempts, args.max_programs), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
