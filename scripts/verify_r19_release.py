from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    with (ROOT / path).open('r', encoding='utf-8') as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    best = load('research/R1_9_CURRENT_BEST.json')
    lock = load('research/R1_9_PRE_FRESH_LOCK.json')
    weights = load('WEIGHTS_MANIFEST_R1_9.json')
    results = load('research/R1_9_RESULTS_MANIFEST.json')

    assert best['candidate_effective_parameters'] == best['parent_effective_parameters'] + best['delta_parameters']
    assert best['candidate_effective_parameters'] < 79_000_000
    assert best['delta_parameters'] < 2_000_000
    assert best['fresh_consumed'] is True
    assert best['delta_sha256'] == lock['checkpoint_sha256'] == results['checkpoint_sha256']
    assert best['parent_sha256'] == lock['parent_sha256']
    assert lock['no_parameter_or_code_tuning_after_fresh'] is True
    assert weights['current_parent']['sha256'] == best['parent_sha256']
    assert weights['current_delta']['sha256'] == best['delta_sha256']
    assert weights['current_delta']['candidate_effective_parameters'] == best['candidate_effective_parameters']
    assert weights['checkpoint_count'] == len(weights['checkpoints']) == 8
    assert len(results['results']) == 3
    assert {r['path'].split('_')[-1].split('.')[0] for r in results['results']} == {'internal', 'dev', 'fresh'}

    for row in results['results']:
        p = ROOT / row['path']
        if p.exists():
            assert p.stat().st_size == row['bytes']
            assert sha256(p) == row['sha256']

    for row in weights['checkpoints']:
        p = ROOT / row['path']
        if p.exists():
            assert p.stat().st_size == row['bytes']
            assert sha256(p) == row['sha256']

    print('R1.9 release integrity OK')


if __name__ == '__main__':
    main()
