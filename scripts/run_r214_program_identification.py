#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.kfigg.r214_program_identification import measure_seed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--cases-per-family', type=int, default=24)
    parser.add_argument('--depth3-cases-per-family', type=int, default=8)
    parser.add_argument('--old-count', type=int, default=40)
    parser.add_argument('--out-of-class-count', type=int, default=24)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    per_seed = [
        measure_seed(
            seed=seed,
            cases_per_family=args.cases_per_family,
            depth3_cases_per_family=args.depth3_cases_per_family,
            old_count=args.old_count,
            out_of_class_count=args.out_of_class_count,
        )
        for seed in args.seeds
    ]
    aggregate = {
        'seeds': args.seeds,
        'per_seed': per_seed,
        'min_main_active_accuracy': min(row['main_accuracy']['active'] for row in per_seed),
        'max_main_active_accuracy': max(row['main_accuracy']['active'] for row in per_seed),
        'min_depth3_active_accuracy': min(row['depth3_accuracy']['active'] for row in per_seed),
        'min_retention_accuracy': min(row['retention_accuracy'] for row in per_seed),
        'min_out_of_class_abstention': min(row['out_of_class_abstention'] for row in per_seed),
        'min_identity_permutation_invariance': min(row['identity_permutation_invariance'] for row in per_seed),
        'false_resolved_accepts_all_active': sum(row['false_resolved_accepts_all_active'] for row in per_seed),
        'max_active_oracle_calls': max(row['max_active_oracle_calls'] for row in per_seed),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
