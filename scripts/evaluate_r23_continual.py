from __future__ import annotations

import argparse
import json

from cogcoder.kfigg23 import evaluate_kfigg23


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--count', type=int, default=200)
    parser.add_argument('--seen-probability', type=float, default=0.35)
    parser.add_argument('--composition-seen-probability', type=float, default=0.25)
    parser.add_argument('--max-depth', type=int, default=3)
    parser.add_argument('--max-candidates', type=int, default=100000)
    parser.add_argument('--demonstrations-per-skill', type=int, default=5)
    args = parser.parse_args()
    result = evaluate_kfigg23(
        seeds=range(args.start, args.start + args.count),
        seen_probability=args.seen_probability,
        composition_seen_probability=args.composition_seen_probability,
        max_depth=args.max_depth,
        max_candidates=args.max_candidates,
        demonstrations_per_skill=args.demonstrations_per_skill,
    )
    result = {k: v for k, v in result.items() if k != 'rows'}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
