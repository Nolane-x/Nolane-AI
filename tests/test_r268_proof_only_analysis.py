from __future__ import annotations

import json

import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch
from benchmarks.kfigg.r268_cross_task_causal_transfer import run_benchmark


def _proof_only(candidates, diagnostic_contexts):
    del diagnostic_contexts
    return sorted(
        candidates,
        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),
    )


def test_r268_proof_only_analysis(monkeypatch):
    monkeypatch.setattr(transfer, '_dedupe_live_candidates', _proof_only)
    monkeypatch.setattr(scratch, '_dedupe_live_candidates', _proof_only)
    result = run_benchmark()
    summary = {
        'positive_transfer_exact': result['positive_transfer_exact'],
        'positive_cases': [
            {
                'name': row['name'],
                'transfer': row['transfer'],
                'tight_scratch': row['tight_scratch'],
                'roomy_scratch': row['roomy_scratch'],
            }
            for row in result['positive_cases']
        ],
    }
    raise AssertionError('PROOF_ONLY_ANALYSIS=' + json.dumps(summary, sort_keys=True))
