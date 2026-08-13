from __future__ import annotations
import argparse
from pathlib import Path
import torch
from cogcoder.edit_training import load_stage2_checkpoint
from cogcoder.neural_system2_curriculum import FrozenStage2ObservationEncoder
from cogcoder.r17_training import load_r17_checkpoint
from train_r17_causal_law_policy import _select
from train_r17_goal_advantage_policy import cache_advantage_rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--start',type=int,required=True); ap.add_argument('--count',type=int,required=True); ap.add_argument('--output',required=True); ap.add_argument('--exploration-steps',type=int,default=6); ap.add_argument('--max-steps',type=int,default=14); args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]; r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'; goal=root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    model,_=load_r17_checkpoint(goal,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
    trunk,tok,_=load_stage2_checkpoint(root/'checkpoints/Nolane-48M-Stage2-Policy.pt'); enc=FrozenStage2ObservationEncoder(trunk,tok,max_length=96)
    episodes=_select(args.start,args.count,exploration_steps=args.exploration_steps,max_steps=args.max_steps); rows=cache_advantage_rows(model,episodes,enc)
    payload=[{'family':r.family,'base_logits':r.base_logits,'policy_features':r.policy_features,'confidence':r.confidence,'label':r.label} for r in rows]
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True); torch.save(payload,path); print({'start':args.start,'count':args.count,'episodes':len(episodes),'rows':len(rows),'bytes':path.stat().st_size},flush=True)
if __name__=='__main__': main()
