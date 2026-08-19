from __future__ import annotations

import json

import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch
from benchmarks.kfigg.r268_cross_task_causal_transfer import run_benchmark


def proof_only(candidates, diagnostic_contexts):
    del diagnostic_contexts
    return sorted(
        candidates,
        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),
    )


def main() -> None:
    transfer._dedupe_live_candidates = proof_only
    scratch._dedupe_live_candidates = proof_only
    result = run_benchmark()
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
