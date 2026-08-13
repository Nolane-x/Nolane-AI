from __future__ import annotations
import copy,json,random,time
from pathlib import Path
import torch
from cogcoder.neural_system2 import system2_parameter_count
from cogcoder.r17_training import checkpoint_metadata_for_report,load_r17_checkpoint,save_r17_checkpoint,sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES,make_r18_task
from cogcoder.r18_executive_training import collect_executive_episode,configure_executive_training,evaluate_executive_episodes,train_executive_epoch
SEED=180818;FIT_START=200;FIT_COUNT=80;VAL_START=280;VAL_COUNT=20;MAX_STEPS=16;EPOCHS=25;LR=1e-3;WEIGHT_DECAY=1e-4;EXPECTED_TRAINABLE=857_857;EXPECTED_EFFECTIVE=77_551_709

def _collect(model,start,count):return [collect_executive_episode(model,make_r18_task(family,'train',index),max_steps=MAX_STEPS) for family in R18_FAMILIES for index in range(start,start+count)]
def _snapshot(model,names):return {n:p.detach().cpu().clone() for n,p in model.named_parameters() if n in names}
def _restore(model,state):
    named=dict(model.named_parameters())
    with torch.no_grad():
        for n,v in state.items():named[n].copy_(v)
def main():
    torch.manual_seed(SEED);random.seed(SEED);torch.set_num_threads(4);root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';parent=root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt';output=root/'checkpoints/Nolane-R1.8-CCSM-ActiveExecutive.pt';result_path=root/'results/r1_8_active_executive_internal.json';result_path.parent.mkdir(parents=True,exist_ok=True)
    model,parent_meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16);names=set(configure_executive_training(model));trainable=sum(p.numel() for p in model.parameters() if p.requires_grad);effective=49_528_677+system2_parameter_count(model)
    if trainable!=EXPECTED_TRAINABLE:raise RuntimeError(f'unexpected executive trainable params: {trainable}')
    if effective!=EXPECTED_EFFECTIVE:raise RuntimeError(f'unexpected effective params: {effective}')
    t0=time.time();fit=_collect(model,FIT_START,FIT_COUNT);val=_collect(model,VAL_START,VAL_COUNT);initial=evaluate_executive_episodes(model,val);print(json.dumps({'event':'precompute','fit_episodes':len(fit),'val_episodes':len(val),'fit_steps':sum(len(e.steps) for e in fit),'val_steps':sum(len(e.steps) for e in val),'seconds':time.time()-t0,'initial':initial},sort_keys=True),flush=True)
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=LR,weight_decay=WEIGHT_DECAY);best_metrics=copy.deepcopy(initial);best_epoch=0;best_state=_snapshot(model,names);history=[]
    for epoch in range(1,EPOCHS+1):
        loss=train_executive_epoch(model,fit,optimizer);metrics=evaluate_executive_episodes(model,val);row={'epoch':epoch,'train_loss':loss,**metrics};history.append(row);print(json.dumps(row,sort_keys=True),flush=True)
        if float(metrics['cross_entropy'])<float(best_metrics['cross_entropy']):best_metrics=copy.deepcopy(metrics);best_epoch=epoch;best_state=_snapshot(model,names)
    _restore(model,best_state);protocol={'families':list(R18_FAMILIES),'fit_indices':[FIT_START,FIT_START+FIT_COUNT],'val_indices':[VAL_START,VAL_START+VAL_COUNT],'seed':SEED,'max_steps':MAX_STEPS,'epochs':EPOCHS,'lr':LR,'weight_decay':WEIGHT_DECAY,'optimizer_updates_per_epoch':'one per cached episode','selection':'lowest validation cross_entropy'};report={'version':'r1.8-active-executive-internal-v1','protocol':protocol,'control_effect_parent_sha256':sha256_file(parent),'control_effect_parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],'candidate_effective_parameters':effective,'trainable_parameters':trainable,'trainable_names':sorted(names),'initial_validation':initial,'best_epoch':best_epoch,'best_validation':best_metrics,'history':history};meta=save_r17_checkpoint(output,model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'r1.8-verified-active-executive','control_effect_parent_sha256':sha256_file(parent),'protocol':protocol,'best_validation':best_metrics});report['checkpoint']=checkpoint_metadata_for_report(meta);result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({'accepted_for_closed_loop_gate':True,'best_epoch':best_epoch,'best_validation':best_metrics,'checkpoint':report['checkpoint']},sort_keys=True),flush=True)
if __name__=='__main__':main()
