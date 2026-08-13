from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import torch

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_crgm_training import (
    collect_crgm_episode,
    crgm_internal_gate,
    crgm_trainable_parameter_names,
    evaluate_crgm_episodes,
    train_crgm_epoch,
)
from cogcoder.r17_training import (
    checkpoint_metadata_for_report,
    load_r17_checkpoint,
    save_r17_checkpoint,
    sha256_file,
)

FAMILIES = ("causal_laws", "causal_switch")


def _collect(model, start: int, count: int, exploration_steps: int, max_steps: int):
    rows=[]
    for family in FAMILIES:
        for index in range(start,start+count):
            rows.append(collect_crgm_episode(model,make_r17_task(family,"train",index),exploration_steps=exploration_steps,max_steps=max_steps))
    return rows


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--fit-start',type=int,default=170); ap.add_argument('--fit-count',type=int,default=16); ap.add_argument('--val-start',type=int,default=186); ap.add_argument('--val-count',type=int,default=8); ap.add_argument('--exploration-steps',type=int,default=6); ap.add_argument('--max-steps',type=int,default=14); ap.add_argument('--epochs',type=int,default=40); ap.add_argument('--lr',type=float,default=5e-4); ap.add_argument('--seed',type=int,default=170617); args=ap.parse_args()
    torch.manual_seed(args.seed); torch.set_num_threads(1)
    root=Path(__file__).resolve().parents[1]; r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'; parent=root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    model,parent_meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
    names=set(crgm_trainable_parameter_names(model,include_policy_scale=False)); params=[]
    for name,p in model.named_parameters(): p.requires_grad_(name in names); params.append(p) if name in names else None
    assert float(model.causal_role_goal_policy_scale.detach())==0.0 and not model.causal_role_goal_policy_scale.requires_grad
    opt=torch.optim.AdamW(params,lr=args.lr,weight_decay=1e-4)
    fit=_collect(model,args.fit_start,args.fit_count,args.exploration_steps,args.max_steps); val=_collect(model,args.val_start,args.val_count,args.exploration_steps,args.max_steps)
    initial=evaluate_crgm_episodes(model,val); best=initial; best_epoch=0; best_state=copy.deepcopy(model.state_dict()); history=[]
    print(json.dumps({'event':'precompute','fit_episodes':len(fit),'fit_steps':sum(len(e.steps) for e in fit),'val_episodes':len(val),'val_steps':sum(len(e.steps) for e in val),'initial':initial},sort_keys=True),flush=True)
    for epoch in range(1,args.epochs+1):
        loss=train_crgm_epoch(model,fit,opt); metrics=evaluate_crgm_episodes(model,val); history.append({'epoch':epoch,'train_loss':loss,**metrics})
        if crgm_internal_gate(metrics) and (best_epoch==0 or metrics['candidate_mse']<best['candidate_mse']): best=metrics; best_epoch=epoch; best_state=copy.deepcopy(model.state_dict())
        print(json.dumps({'epoch':epoch,'train_loss':loss,'candidate_mse':metrics['candidate_mse'],'baseline_mse':metrics['baseline_mse'],'candidate_rank_accuracy':metrics['candidate_rank_accuracy'],'baseline_rank_accuracy':metrics['baseline_rank_accuracy'],'families':metrics['families']},sort_keys=True),flush=True)
    model.load_state_dict(best_state); accepted=best_epoch>0 and crgm_internal_gate(best)
    report={'version':'r1.7-crgm-internal-v1','protocol':vars(args),'parent_sha256':sha256_file(parent),'parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],'trainable_parameters':sum(p.numel() for p in params),'trainable_names':sorted(names),'policy_scale':float(model.causal_role_goal_policy_scale.detach()),'initial_validation':initial,'best_epoch':best_epoch,'best_validation':best,'accepted_for_policy_calibration':accepted,'history':history}
    rp=root/'results/r1_7_crgm_internal.json'; rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted: print(json.dumps({'accepted':False,'best_epoch':best_epoch,'best':best},sort_keys=True),flush=True); raise SystemExit(2)
    if float(model.causal_role_goal_policy_scale.detach())!=0.0: raise RuntimeError('CRGM world-model gate must keep policy scale zero')
    meta=save_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-CRGM.pt',model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'crgm-world-model','parent_sha256':sha256_file(parent),'internal_gate':best}); report['checkpoint']=checkpoint_metadata_for_report(meta); rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps({'accepted':True,'best_epoch':best_epoch,'best':best,'checkpoint':report['checkpoint']},sort_keys=True),flush=True)

if __name__=='__main__': main()
