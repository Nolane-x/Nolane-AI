from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from cogcoder.arc_eval import load_task
from cogcoder.arc_grid import components, infer_background
from cogcoder.arc_score_current import score_current


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
    x, y = a.colors, b.colors
    if x == y:
        return 'same_set'
    if x <= y:
        return 'input_subset'
    if y <= x:
        return 'output_subset'
    return 'changed'


def _separator(g):
    for r in range(1, g.h - 1):
        if len(set(g.rows[r])) == 1:
            return True
    for c in range(1, g.w - 1):
        if len({g.cell(r, c) for r in range(g.h)}) == 1:
            return True
    return False


def _comp_count(g):
    return len(components(g, background=infer_background(g), connectivity=4))


def summarize(directory, *, examples=6):
    buckets = Counter()
    sample = defaultdict(list)
    solved = 0
    for path in sorted(Path(directory).glob('*.json')):
        task = load_task(path)
        score = score_current(task, max_attempts=2, max_programs=64)
        solved += int(score.solved)
        if score.solved:
            continue
        shape_labels = {_shape(a, b) for a, b in task.train_pairs}
        color_labels = {_colors(a, b) for a, b in task.train_pairs}
        comp_delta = []
        sep = False
        for a, b in task.train_pairs:
            ca, cb = _comp_count(a), _comp_count(b)
            comp_delta.append('same' if ca == cb else ('increase' if cb > ca else 'decrease'))
            sep = sep or _separator(a)
        key = (
            next(iter(shape_labels)) if len(shape_labels) == 1 else 'mixed_shape',
            next(iter(color_labels)) if len(color_labels) == 1 else 'mixed_color',
            next(iter(set(comp_delta))) if len(set(comp_delta)) == 1 else 'mixed_components',
            'separator' if sep else 'plain',
        )
        buckets[key] += 1
        if len(sample[key]) < examples:
            sample[key].append(path.stem)
    rows = [
        {'count': count, 'key': list(key), 'examples': sample[key]}
        for key, count in buckets.most_common()
    ]
    return {'cases': sum(1 for _ in Path(directory).glob('*.json')), 'solved': solved, 'remaining': sum(buckets.values()), 'buckets': rows}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--examples', type=int, default=6)
    a = p.parse_args()
    print(json.dumps(summarize(a.directory, examples=a.examples), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
