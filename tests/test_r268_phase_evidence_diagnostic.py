from __future__ import annotations

import json
from pathlib import Path

from benchmarks.kfigg.r268_adaptive_causal_basis import run_benchmark


def _diffs(a, b, path='$', out=None):
    if out is None:
        out = []
    if type(a) is not type(b):
        out.append((path, 'TYPE', type(a).__name__, type(b).__name__))
        return out
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        for key in sorted(ka - kb):
            out.append((f'{path}.{key}', 'MISSING_RECOMPUTED', a[key], None))
        for key in sorted(kb - ka):
            out.append((f'{path}.{key}', 'EXTRA_RECOMPUTED', None, b[key]))
        for key in sorted(ka & kb):
            _diffs(a[key], b[key], f'{path}.{key}', out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((path, 'LEN', len(a), len(b)))
        for index, (left, right) in enumerate(zip(a, b)):
            _diffs(left, right, f'{path}[{index}]', out)
    elif a != b:
        out.append((path, 'VALUE', a, b))
    return out


def test_frozen_phase_evidence_diagnostic() -> None:
    frozen = json.loads(Path('R2_68_PHASE_A_RESULT.json').read_text())
    current = run_benchmark()
    delta = _diffs(frozen, current)
    if delta:
        rendered = '\n'.join(json.dumps(row, default=str) for row in delta[:120])
        raise AssertionError(f'R2.68 frozen Phase A mismatch: {len(delta)} differences\n{rendered}')
