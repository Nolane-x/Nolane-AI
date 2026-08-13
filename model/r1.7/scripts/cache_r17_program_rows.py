from __future__ import annotations

import argparse
from pathlib import Path
import torch

from cogcoder.edit_training import load_stage2_checkpoint
from cogcoder.neural_system2_curriculum import FrozenStage2ObservationEncoder
from cogcoder.r17_program_training import build_program_rows
from cogcoder.r17_training import load_r17_checkpoint
from train_r17_causal_law_policy import _build_episode
from train_r17_goal_advantage_policy import cache_advantage_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--count', type=int, required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--max-steps', type=int, default=8)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    r12 = root / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    r16 = root / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'
    parent = root / 'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    model, _ = load_r17_checkpoint(parent, expected_r1_2_checkpoint=r12, expected_r1_6_parent_checkpoint=r16)
    trunk, tokenizer, _ = load_stage2_checkpoint(root / 'checkpoints/Nolane-48M-Stage2-Policy.pt')
    encoder = FrozenStage2ObservationEncoder(trunk, tokenizer, max_length=96)
    indices = list(range(args.start, args.start + args.count))
    episodes = [_build_episode('composition_holdout', i, exploration_steps=0, max_steps=args.max_steps) for i in indices]
    cached = cache_advantage_rows(model, episodes, encoder)
    rows = build_program_rows(episodes, cached, [i % 8 for i in indices])
    payload = [
        {
            'template_id': row.template_id,
            'program_step': row.program_step,
            'base_logits': row.base_logits,
            'policy_features': row.policy_features,
            'label': row.label,
            'is_submit': row.is_submit,
        }
        for row in rows
    ]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    print({'start': args.start, 'count': args.count, 'worlds': len(episodes), 'rows': len(rows), 'templates': sorted(set(i % 8 for i in indices)), 'bytes': path.stat().st_size}, flush=True)


if __name__ == '__main__':
    main()
