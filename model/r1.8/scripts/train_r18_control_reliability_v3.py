from __future__ import annotations
import json,random
from pathlib import Path
import torch,torch.nn.functional as F
from cogcoder.r17_training import checkpoint_metadata_for_report,load_r17_checkpoint,save_r17_checkpoint,sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES,make_r18_task
from cogcoder.r18_control_reliability import collect_control_reliability_rows,configure_control_reliability_training
from cogcoder.r18_reliability_training import ReliabilityTrainingRow,calibrate_learned_certificate,learned_certificate_scores
SEED=180618;FIT_START=92;FIT_COUNT=12;VAL_START=104;VAL_COUNT=8;SAFE_MSE=.01;EXPLORATION_STEPS=6;MAX_STEPS=16;EPOCHS=100;LR=1e-3;WEIGHT_DECAY=1e-4;BATCH_SIZE=512;THRESHOLDS=(.5,.6,.7,.8,.9,.95,.975);REQUIRED_PRECISION=.95;MIN_COVERAGE=.20;MIN_FAMILY_COVERAGE=.10

def _collect(model,start,count):
    rows=[]
    for family in R18_FAMILIES:
        for index in range(start,start+count):rows.extend(collect_control_reliability_rows(model,make_r18_task(family,'train',index),safe_mse=SAFE_MSE,exploration_steps=EXPLORATION_STEPS,max_steps=MAX_STEPS))
    return rows
def _stack(rows):return torch.stack([r.hidden for r in rows]),torch.stack([r.evidence_meta for r in rows]),torch.tensor([r.safe for r in rows],dtype=torch.float32),torch.tensor([r.prediction_mse for r in rows],dtype=torch.float32),[r.family for r in rows]
def _bce(model,h,y):
    model.eval()
    with torch.no_grad():return float(F.binary_cross_entropy_with_logits(model.conditional_law_confidence_head(h).squeeze(-1),y).item())
def main():
    torch.manual_seed(SEED);random.seed(SEED);torch.set_num_threads(4);root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';parent=root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt';output=root/'checkpoints/Nolane-R1.8-CCSM-CertifiedControl.pt';result_path=root/'results/r1_8_control_reliability_v3.json';result_path.parent.mkdir(parents=True,exist_ok=True)
    model,parent_meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16);fit_rows=_collect(model,FIT_START,FIT_COUNT);val_rows=_collect(model,VAL_START,VAL_COUNT);fit_h,fit_m,fit_y,fit_err,fit_f=_stack(fit_rows);val_h,val_m,val_y,val_err,val_f=_stack(val_rows);names=set(configure_control_reliability_training(model));params=[p for p in model.parameters() if p.requires_grad];assert sum(p.numel() for p in params)==257;optimizer=torch.optim.AdamW(params,lr=LR,weight_decay=WEIGHT_DECAY);initial_bce=_bce(model,val_h,val_y);best_bce=initial_bce;best_epoch=0;best_state={n:p.detach().cpu().clone() for n,p in model.named_parameters() if n in names};history=[]
    for epoch in range(1,EPOCHS+1):
        model.train();order=torch.randperm(len(fit_h));total=0.;batches=0
        for start in range(0,len(order),BATCH_SIZE):
            index=order[start:start+BATCH_SIZE];optimizer.zero_grad(set_to_none=True);logits=model.conditional_law_confidence_head(fit_h[index]).squeeze(-1);loss=F.binary_cross_entropy_with_logits(logits,fit_y[index]);loss.backward();optimizer.step();total+=float(loss.detach());batches+=1
        val_bce=_bce(model,val_h,val_y);history.append({'epoch':epoch,'train_bce':total/max(1,batches),'val_bce':val_bce})
        if val_bce<best_bce:best_bce=val_bce;best_epoch=epoch;best_state={n:p.detach().cpu().clone() for n,p in model.named_parameters() if n in names}
    named=dict(model.named_parameters())
    with torch.no_grad():
        for n,v in best_state.items():named[n].copy_(v)
        confidence=torch.sigmoid(model.conditional_law_confidence_head(val_h).squeeze(-1));scores=learned_certificate_scores(confidence.unsqueeze(1),val_m.unsqueeze(1)).squeeze(1)
    rows=[ReliabilityTrainingRow(val_f[i],float(scores[i]),float(val_err[i])) for i in range(len(val_h))]
    try:gate=calibrate_learned_certificate(rows,thresholds=THRESHOLDS,acceptable_mse=SAFE_MSE,required_precision=REQUIRED_PRECISION,min_coverage=MIN_COVERAGE,min_family_coverage=MIN_FAMILY_COVERAGE);accepted=True
    except RuntimeError:gate=None;accepted=False
    protocol={'families':list(R18_FAMILIES),'fit_indices':[FIT_START,FIT_START+FIT_COUNT],'val_indices':[VAL_START,VAL_START+VAL_COUNT],'seed':SEED,'safe_mse':SAFE_MSE,'exploration_steps':EXPLORATION_STEPS,'max_steps':MAX_STEPS,'epochs':EPOCHS,'lr':LR,'weight_decay':WEIGHT_DECAY,'batch_size':BATCH_SIZE,'thresholds':list(THRESHOLDS),'required_precision':REQUIRED_PRECISION,'min_coverage':MIN_COVERAGE,'min_family_coverage':MIN_FAMILY_COVERAGE};report={'version':'r1.8-control-reliability-v3','control_effect_parent_sha256':sha256_file(parent),'control_effect_parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],'protocol':protocol,'fit_rows':len(fit_rows),'val_rows':len(val_rows),'initial_val_bce':initial_bce,'best_epoch':best_epoch,'best_val_bce':best_bce,'val_safe_rate':float(val_y.mean()),'accepted_for_active_control':accepted,'gate':gate.__dict__ if gate else None,'history':history};result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted:print(json.dumps({'accepted':False,'best_epoch':best_epoch,'initial_val_bce':initial_bce,'best_val_bce':best_bce,'val_safe_rate':report['val_safe_rate']},sort_keys=True));raise SystemExit(2)
    meta=save_r17_checkpoint(output,model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'r1.8-control-reliability-v3','control_effect_parent_sha256':sha256_file(parent),'protocol':protocol,'gate':gate.__dict__});report['checkpoint']=checkpoint_metadata_for_report(meta);result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({'accepted':True,'best_epoch':best_epoch,'initial_val_bce':initial_bce,'best_val_bce':best_bce,'gate':gate.__dict__,'checkpoint':report['checkpoint']},sort_keys=True))
if __name__=='__main__':main()
