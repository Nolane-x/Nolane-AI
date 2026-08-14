from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from cogcoder import r25_n as base
from cogcoder.arc_eval import load_task
from cogcoder.arc_grid import components, infer_background
from cogcoder.r25_n2 import _program_set as frozen_program_set
from cogcoder.r26_split import partition_paths


def _shape(a, b):
    if a.shape == b.shape:
        return 'same'
    if b.h % a.h == 0 and b.w % a.w == 0:
        return 'integer_expand'
    if a.h % b.h == 0 and a.w % b.w == 0:
        return 'integer_shrink'
    if b.h >= a.h and b.w >= a.w:
        return 'expand'
    if b.h <= a.h and b.w <= a.w:
        return 'shrink'
    return 'reshape'


def _colors(a, b):
    if a.colors == b.colors:
        return 'same_set'
    if a.colors <= b.colors:
        return 'input_subset'
    if b.colors <= a.colors:
        return 'output_subset'
    return 'changed'


def _component_delta(a, b):
    ca = len(components(a, background=infer_background(a), connectivity=4))
    cb = len(components(b, background=infer_background(b), connectivity=4))
    return 'same' if ca == cb else ('increase' if cb > ca else 'decrease')


def _period(values):
    n = len(values)
    for p in range(1, n // 2 + 1):
        if all(values[i] == values[i % p] for i in range(n)):
            return p
    return 0


def _periodic(grid):
    row_p = _period(grid.rows)
    cols = tuple(tuple(grid.cell(r, c) for r in range(grid.h)) for c in range(grid.w))
    col_p = _period(cols)
    if row_p and col_p:
        return 'both'
    if row_p:
        return 'rows'
    if col_p:
        return 'cols'
    return 'none'


def _change_geometry(a, b):
    if a.shape != b.shape:
        return 'shape_change'
    changed = [(r, c) for r in range(a.h) for c in range(a.w) if a.cell(r, c) != b.cell(r, c)]
    if not changed:
        return 'none'
    frac = len(changed) / (a.h * a.w)
    rows = Counter(r for r, _ in changed)
    cols = Counter(c for _, c in changed)
    full_rows = sum(1 for count in rows.values() if count == a.w)
    full_cols = sum(1 for count in cols.values() if count == a.h)
    if full_rows and full_cols:
        geometry = 'cross_spans'
    elif full_rows:
        geometry = 'row_spans'
    elif full_cols:
        geometry = 'col_spans'
    elif len(rows) == 1:
        geometry = 'one_row'
    elif len(cols) == 1:
        geometry = 'one_col'
    else:
        r0, r1 = min(rows), max(rows)
        c0, c1 = min(cols), max(cols)
        bbox_area = (r1 - r0 + 1) * (c1 - c0 + 1)
        fill = len(changed) / bbox_area
        geometry = 'compact' if fill >= 0.6 else 'scattered'
    density = 'sparse' if frac <= 0.10 else ('medium' if frac <= 0.40 else 'dense')
    return f'{density}:{geometry}'


def _uniform(labels):
    labels = set(labels)
    return next(iter(labels)) if len(labels) == 1 else 'mixed'


def _baseline_score(task):
    previous = base.program_set
    base.program_set = frozen_program_set
    try:
        return base.score(task, 2, 64)
    finally:
        base.program_set = previous


def profile(directory: str | Path, *, examples: int = 5, top: int = 30):
    all_paths = tuple(sorted(Path(directory).glob('*.json'), key=lambda p: p.name))
    development, heldout = partition_paths(all_paths)
    del heldout
    buckets = Counter()
    sample = defaultdict(list)
    solved = errors = 0
    for path in development:
        try:
            task = load_task(path)
            score = _baseline_score(task)
        except Exception:
            errors += 1
            continue
        solved += int(score.solved)
        if score.solved:
            continue
        key = (
            _uniform(_shape(a, b) for a, b in task.train_pairs),
            _uniform(_colors(a, b) for a, b in task.train_pairs),
            _uniform(_component_delta(a, b) for a, b in task.train_pairs),
            _uniform(_change_geometry(a, b) for a, b in task.train_pairs),
            _uniform(_periodic(a) for a, _ in task.train_pairs),
        )
        buckets[key] += 1
        if len(sample[key]) < examples:
            sample[key].append(path.stem)
    rows = [
        {
            'count': count,
            'shape': key[0],
            'colors': key[1],
            'components': key[2],
            'change_geometry': key[3],
            'input_periodicity': key[4],
            'examples': sample[key],
        }
        for key, count in buckets.most_common(top)
    ]
    return {
        'partition': 'development',
        'cases': len(development),
        'baseline_solved': solved,
        'remaining': sum(buckets.values()),
        'errors': errors,
        'top_buckets': rows,
        'internal_heldout_loaded': False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--examples', type=int, default=5)
    p.add_argument('--top', type=int, default=30)
    a = p.parse_args()
    print(json.dumps(profile(a.directory, examples=a.examples, top=a.top), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
