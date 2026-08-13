from __future__ import annotations
import copy,json,random
from pathlib import Path
import torch
from cogcoder.r17_goal_training import goal_difference_advantage_trainable_parameter_names
from cogcoder.r17_training import checkpoint_metadata_for_report,load_r17_checkpoint,save_r17_checkpoint
from train_r17_goal_advantage_policy import GoalAdvantageRow,groups,objective,causal_score,preservation_score

def load_rows(paths):
    rows=[]
    for path in paths: rows.extend(GoalAdvantageRow(**item) for item in torch.load(path,map_location='cpu',weights_only=False))
    return rows

def main():
    seed=170517; epochs=60; lr=0.005
    torch.manual_seed(seed); random.seed(seed)
    root=Path(__file__).resolve().parents[1]; r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'; goal=root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    model,_=load_r17_checkpoint(goal,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
    fit=load_rows([root/f'cache/r17_goal_advantage/fit-{s}.pt' for s in (96,99,102,105)]); val=load_rows([root/'cache/r17_goal_advantage/val-108.pt']); fg=groups(fit); vg=groups(val)
    for p in model.parameters(): p.requires_grad_(False)
    names=set(goal_difference_advantage_trainable_parameter_names(model)); params=[]
    for name,p in model.named_parameters():
        if name in names: p.requires_grad_(True); params.append(p)
    assert sum(p.numel() for p in params)==385
    opt=torch.optim.AdamW(params,lr=lr,weight_decay=1e-4)
    with torch.no_grad(): base_loss,base=objective(model,vg)
    best_loss=float(base_loss); best_epoch=0; best_state=copy.deepcopy(model.state_dict()); best_metrics=copy.deepcopy(base); history=[]
    for epoch in range(1,epochs+1):
        opt.zero_grad(set_to_none=True); loss,fitm=objective(model,fg); loss.backward(); torch.nn.utils.clip_grad_norm_(params,1.0); opt.step()
        with torch.no_grad(): vl,vm=objective(model,vg)
        valid=(float(vl)<float(base_loss) and vm['accuracy']>=base['accuracy'] and causal_score(vm)>causal_score(base) and preservation_score(vm)>=preservation_score(base))
        if valid and float(vl)<best_loss: best_loss=float(vl); best_epoch=epoch; best_state=copy.deepcopy(model.state_dict()); best_metrics=copy.deepcopy(vm)
        history.append({'epoch':epoch,'fit_loss':float(loss.detach()),'val_loss':float(vl),'fit':fitm,'val':vm})
    model.load_state_dict(best_state); accepted=best_epoch>0
    report={'version':'r1.7-goal-advantage-policy-internal-v1','protocol':{'fit_indices':[96,108],'val_indices':[108,112],'families':['causal_laws','causal_switch','goal_inference','composition_holdout'],'seed':seed,'epochs':epochs,'lr':lr,'weight_decay':1e-4,'cached_full_parent_rows':True},'fit_rows':len(fit),'val_rows':len(val),'base_loss':float(base_loss),'base_metrics':base,'best_epoch':best_epoch,'best_loss':best_loss,'best_metrics':best_metrics,'accepted_for_dev':accepted,'trainable_parameters':385,'history':history}
    rp=root/'results/r1_7_goal_advantage_internal.json'; rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted: print(json.dumps({'accepted':False,'base':base,'best':best_metrics,'best_epoch':best_epoch},sort_keys=True),flush=True); raise SystemExit(2)
    meta=save_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-GoalAdvantage.pt',model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'goal_advantage_internal':report}); report['checkpoint']=checkpoint_metadata_for_report(meta); rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps({'accepted':True,'base':base,'best':best_metrics,'best_epoch':best_epoch,'best_loss':best_loss,'checkpoint':report['checkpoint']},sort_keys=True),flush=True)
if __name__=='__main__': main()
