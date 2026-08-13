from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import torch

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_operator_training import (
    collect_operator_transitions,
    evaluate_operator_transitions,
    operator_executor_internal_gate,
    operator_executor_trainable_parameter_names,
    restore_trainable_state,
    snapshot_trainable_state,
    train_operator_epoch,
)
from cogcoder.r17_training import checkpoint_metadata_for_report, load_r17_checkpoint, save_r17_checkpoint, sha256_file


def _collect(start: int, count: int):
    rows=[]
    for index in range(start,start+count):
        rows.extend(collect_operator_transitions(make_r17_task('composition_holdout','train',index)))
    return rows


def _atomic_save(payload, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    torch.save(payload, tmp)
    tmp.replace(path)


def main():
    seed=170917; epochs=80; lr=0.002; batch_size=128
    protocol={'seed':seed,'epochs':epochs,'lr':lr,'weight_decay':1e-4,'batch_size':batch_size,'fit_indices':[282,482],'val_indices':[482,522]}
    torch.manual_seed(seed); random.seed(seed); torch.set_num_threads(4)
    root=Path(__file__).resolve().parents[1]
    r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'; parent=root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    run_state_path=root/'cache/r17_operator/run_state.pt'
    model,parent_meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
    names=set(operator_executor_trainable_parameter_names(model)); params=[]
    for name,p in model.named_parameters():
        p.requires_grad_(name in names)
        if name in names: params.append(p)
    assert sum(p.numel() for p in params)==359_568
    fit=_collect(282,200); val=_collect(482,40)
    assert len(fit)==1000 and len(val)==200
    optimizer=torch.optim.AdamW(params,lr=lr,weight_decay=1e-4)

    initial=evaluate_operator_transitions(model,val)
    best=None;best_epoch=0;best_state=None;history=[];start_epoch=1
    if run_state_path.exists():
        state=torch.load(run_state_path,map_location='cpu',weights_only=False)
        if state.get('version')!='r17-operator-resume-v1' or state.get('protocol')!=protocol:
            raise RuntimeError('operator resume state protocol mismatch')
        restore_trainable_state(model,state['executor_state'])
        optimizer.load_state_dict(state['optimizer_state'])
        initial=state['initial_validation'];best=state['best_validation'];best_epoch=int(state['best_epoch']);best_state=state['best_executor_state'];history=list(state['history']);start_epoch=int(state['epoch'])+1
        torch.set_rng_state(state['torch_rng_state'])
        print(json.dumps({'event':'resume','completed_epoch':int(state['epoch']),'next_epoch':start_epoch,'best_epoch':best_epoch},sort_keys=True),flush=True)
    else:
        print(json.dumps({'event':'precompute','fit_rows':len(fit),'val_rows':len(val),'initial':initial},sort_keys=True),flush=True)

    for epoch in range(start_epoch,epochs+1):
        loss=train_operator_epoch(model,fit,optimizer,batch_size=batch_size);metrics=evaluate_operator_transitions(model,val);history.append({'epoch':epoch,'train_loss':loss,**metrics})
        print(json.dumps({'epoch':epoch,'train_loss':loss,**metrics},sort_keys=True),flush=True)
        if operator_executor_internal_gate(metrics):
            key=(metrics['exact_vector_accuracy'],metrics['element_accuracy'])
            old=(-1.0,-1.0) if best is None else (best['exact_vector_accuracy'],best['element_accuracy'])
            if key>old:
                best=copy.deepcopy(metrics);best_epoch=epoch;best_state=snapshot_trainable_state(model,names)
        _atomic_save({
            'version':'r17-operator-resume-v1','protocol':protocol,'epoch':epoch,
            'executor_state':snapshot_trainable_state(model,names),
            'optimizer_state':optimizer.state_dict(),'torch_rng_state':torch.get_rng_state(),
            'initial_validation':initial,'best_validation':best,'best_epoch':best_epoch,
            'best_executor_state':best_state,'history':history,
        },run_state_path)

    accepted=best is not None
    if accepted: restore_trainable_state(model,best_state)
    report={'version':'r1.7-operator-executor-internal-v1','protocol':protocol,'parent_sha256':sha256_file(parent),'parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],'trainable_parameters':sum(p.numel() for p in params),'fit_rows':len(fit),'val_rows':len(val),'initial_validation':initial,'best_epoch':best_epoch,'best_validation':best,'accepted_for_program_search':accepted,'history':history,'resume_state':{'completed_epoch':epochs,'path':str(run_state_path.relative_to(root))}}
    rp=root/'results/r1_7_operator_executor_internal.json';rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted:
        print(json.dumps({'accepted':False,'best_epoch':0,'initial':initial},sort_keys=True),flush=True);raise SystemExit(2)
    meta=save_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt',model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'neural-operator-executor','internal_gate':best});report['checkpoint']=checkpoint_metadata_for_report(meta);rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({'accepted':True,'best_epoch':best_epoch,'best':best,'checkpoint':report['checkpoint']},sort_keys=True),flush=True)

if __name__=='__main__':main()
