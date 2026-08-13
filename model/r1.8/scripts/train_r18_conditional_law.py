from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path

import torch

from cogcoder.r17_training import checkpoint_metadata_for_report, load_r17_checkpoint, save_r17_checkpoint, sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES, make_r18_task
from cogcoder.r18_training import collect_conditional_law_episode, conditional_law_internal_gate, configure_conditional_law_training, evaluate_conditional_law_episodes, train_conditional_law_epoch

SEED=180318; FIT_START=0; FIT_COUNT=24; VAL_START=24; VAL_COUNT=8; EXPLORATION_STEPS=6; MAX_STEPS=16; EPOCHS=30; LR=3e-4; WEIGHT_DECAY=1e-4; BATCH_SIZE=128; EXPECTED_TRAINABLE=1_231_873

def _collect(model,start,count):
    return [collect_conditional_law_episode(model,make_r18_task(family,'train',index),exploration_steps=EXPLORATION_STEPS,max_steps=MAX_STEPS) for family in R18_FAMILIES for index in range(start,start+count)]
def _snapshot(model,names): return {n:p.detach().cpu().clone() for n,p in model.named_parameters() if n in names}
def _restore(model,state):
    named=dict(model.named_parameters())
    with torch.no_grad():
        for n,v in state.items(): named[n].copy_(v)

def main():
    torch.manual_seed(SEED); random.seed(SEED); torch.set_num_threads(4); root=Path(__file__).resolve().parents[1]
    r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'; parent=root/'checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt'; output=root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt'; result_path=root/'results/r1_8_conditional_law_internal.json'; result_path.parent.mkdir(parents=True,exist_ok=True)
    model,parent_meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16); names=set(configure_conditional_law_training(model)); trainable=sum(p.numel() for p in model.parameters() if p.requires_grad)
    if trainable!=EXPECTED_TRAINABLE: raise RuntimeError(f'unexpected trainable parameter count: {trainable}')
    t0=time.time(); fit=_collect(model,FIT_START,FIT_COUNT); val=_collect(model,VAL_START,VAL_COUNT); initial=evaluate_conditional_law_episodes(model,val,batch_size=BATCH_SIZE); print(json.dumps({'event':'precompute','fit_episodes':len(fit),'val_episodes':len(val),'seconds':time.time()-t0,'initial':initial},sort_keys=True),flush=True)
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=LR,weight_decay=WEIGHT_DECAY); best_metrics=None; best_epoch=0; best_state=None; history=[]
    for epoch in range(1,EPOCHS+1):
        loss=train_conditional_law_epoch(model,fit,optimizer,batch_size=BATCH_SIZE); metrics=evaluate_conditional_law_episodes(model,val,batch_size=BATCH_SIZE); row={'epoch':epoch,'train_loss':loss,**metrics}; history.append(row); print(json.dumps(row,sort_keys=True),flush=True)
        if conditional_law_internal_gate(metrics) and (best_metrics is None or float(metrics['candidate_mse'])<float(best_metrics['candidate_mse'])):
            best_epoch=epoch; best_metrics=copy.deepcopy(metrics); best_state=_snapshot(model,names)
    accepted=best_state is not None and best_metrics is not None
    if accepted:_restore(model,best_state)
    protocol={'families':list(R18_FAMILIES),'fit_indices':[FIT_START,FIT_START+FIT_COUNT],'val_indices':[VAL_START,VAL_START+VAL_COUNT],'seed':SEED,'exploration_steps':EXPLORATION_STEPS,'max_steps':MAX_STEPS,'epochs':EPOCHS,'lr':LR,'weight_decay':WEIGHT_DECAY,'batch_size':BATCH_SIZE}
    report={'version':'r1.8-conditional-law-internal-v1','protocol':protocol,'phase_c_parent_sha256':sha256_file(parent),'phase_c_parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],'trainable_parameters':trainable,'trainable_names':sorted(names),'initial_validation':initial,'best_epoch':best_epoch,'best_validation':best_metrics,'accepted_for_reliability_calibration':accepted,'history':history}; result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted: print(json.dumps({'accepted':False,'best_epoch':0,'initial':initial},sort_keys=True),flush=True); raise SystemExit(2)
    meta=save_r17_checkpoint(output,model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'r1.8-conditional-neural-law-prior','phase_c_parent_sha256':sha256_file(parent),'protocol':protocol,'internal_gate':best_metrics}); report['checkpoint']=checkpoint_metadata_for_report(meta); result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps({'accepted':True,'best_epoch':best_epoch,'best':best_metrics,'checkpoint':report['checkpoint']},sort_keys=True),flush=True)

if __name__=='__main__': main()
