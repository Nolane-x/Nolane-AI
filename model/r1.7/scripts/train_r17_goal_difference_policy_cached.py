from __future__ import annotations

import copy
import json
import random
from pathlib import Path
import torch

from cogcoder.r17_goal_training import goal_difference_policy_trainable_parameter_names
from cogcoder.r17_training import checkpoint_metadata_for_report, load_r17_checkpoint, save_r17_checkpoint
from train_r17_goal_difference_policy import GoalPolicyRow, _groups, _objective, _causal_score, _preservation_score


def _load_rows(paths):
    rows=[]
    for path in paths:
        for item in torch.load(path,map_location='cpu',weights_only=False):
            rows.append(GoalPolicyRow(**item))
    return rows


def main() -> None:
    seed=170417; epochs=120; lr=0.05
    torch.manual_seed(seed); random.seed(seed)
    root=Path(__file__).resolve().parents[1]
    r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'
    goal=root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    model,_=load_r17_checkpoint(goal,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
    fit_paths=[root/f'cache/r17_goal_policy/fit-{s}.pt' for s in (80,83,86,89)]
    val_paths=[root/'cache/r17_goal_policy/val-92.pt']
    fit_rows=_load_rows(fit_paths); val_rows=_load_rows(val_paths)
    fg=_groups(fit_rows); vg=_groups(val_rows)
    for p in model.parameters(): p.requires_grad_(False)
    names=goal_difference_policy_trainable_parameter_names(model)
    assert names==['goal_difference_policy_scale']
    scale=dict(model.named_parameters())['goal_difference_policy_scale']; scale.requires_grad_(True)
    opt=torch.optim.Adam([scale],lr=lr)
    with torch.no_grad(): base_loss,base=_objective(scale,vg)
    best_loss=float(base_loss); best_epoch=0; best_scale=scale.detach().clone(); best_metrics=copy.deepcopy(base); history=[]
    for epoch in range(1,epochs+1):
        opt.zero_grad(set_to_none=True); loss,fit=_objective(scale,fg); loss.backward(); opt.step()
        with torch.no_grad(): vl,vm=_objective(scale,vg)
        valid=(float(vl)<float(base_loss) and vm['accuracy']>=base['accuracy'] and _causal_score(vm)>_causal_score(base) and _preservation_score(vm)>=_preservation_score(base))
        if valid and float(vl)<best_loss:
            best_loss=float(vl); best_epoch=epoch; best_scale=scale.detach().clone(); best_metrics=copy.deepcopy(vm)
        history.append({'epoch':epoch,'fit_loss':float(loss.detach()),'val_loss':float(vl),'fit':fit,'val':vm,'scale':float(torch.tanh(scale).detach())})
    with torch.no_grad(): scale.copy_(best_scale)
    accepted=best_epoch>0
    report={
        'version':'r1.7-goal-difference-policy-internal-v1',
        'protocol':{'fit_indices':[80,92],'val_indices':[92,96],'families':['causal_laws','causal_switch','goal_inference','composition_holdout'],'seed':seed,'epochs':epochs,'lr':lr,'cached_full_parent_rows':True},
        'fit_rows':len(fit_rows),'val_rows':len(val_rows),'base_loss':float(base_loss),'base_metrics':base,'best_epoch':best_epoch,'best_loss':best_loss,'best_metrics':best_metrics,
        'accepted_for_dev':accepted,'trainable_parameters':1,'scale':float(torch.tanh(scale).detach()),'history':history,
    }
    rp=root/'results/r1_7_goal_difference_policy_internal.json'; rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted:
        print(json.dumps({'accepted':False,'base':base,'best':best_metrics,'best_epoch':best_epoch},sort_keys=True),flush=True); raise SystemExit(2)
    meta=save_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-GoalDifferencePolicy.pt',model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'goal_difference_policy_internal':report})
    report['checkpoint']=checkpoint_metadata_for_report(meta); rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'accepted':True,'base':base,'best':best_metrics,'best_epoch':best_epoch,'best_loss':best_loss,'scale':report['scale'],'checkpoint':report['checkpoint']},sort_keys=True),flush=True)

if __name__=='__main__': main()
