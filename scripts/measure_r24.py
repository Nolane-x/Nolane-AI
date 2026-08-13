from __future__ import annotations

import argparse
import json

from cogcoder.kfigg24 import evaluate_kfigg24


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start', type=int, required=True)
    p.add_argument('--count', type=int, default=200)
    p.add_argument('--max-steps', type=int, default=26)
    p.add_argument('--retry-budget', type=int, default=2)
    a = p.parse_args()
    result = evaluate_kfigg24(
        seeds=range(a.start, a.start + a.count),
        max_steps=a.max_steps,
        retry_budget=a.retry_budget,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
