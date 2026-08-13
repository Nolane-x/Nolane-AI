from __future__ import annotations
import json,random
from pathlib import Path
import torch,torch.nn.functional as F
from cogcoder.r17_training import checkpoint_metadata_for_report,load_r17_checkpoint,save_r17_checkpoint,sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES,make_r18_task
from cogcoder.r18_reliability_training import ReliabilityTrainingRow,calibrate_learned_certificate,configure_reliability_training,learned_certificate_scores
from cogcoder.r18_training import collect_conditional_law_episode
SEED=180418;FIT_START=48;FIT_COUNT=12;VAL_START=60;VAL_COUNT=8;EPOCHS=100;LR=1e-3;WEIGHT_DECAY=1e-4;BATCH_SIZE=512;THRESHOLDS=(.5,.6,.7,.8,.9,.95,.975);ACCEPTABLE_MSE=.005;REQUIRED_PRECISION=.95;MIN_COVERAGE=.20;MIN_FAMILY_COVERAGE=.10

def _cache(model,start,count):
    hidden=[];meta=[];safe=[];mse=[];family=[];model.eval()
    with torch.no_grad():
        for fam in R18_FAMILIES:
            for index in range(start,start+count):
                ep=collect_conditional_law_episode(model,make_r18_task(fam,'train',index),exploration_steps=6,max_steps=16)
                for step in ep.steps:
                    out=model.conditional_law_scores(step.state_sketch.unsqueeze(0),step.context_fingerprint.unsqueeze(0),step.action_embeddings.unsqueeze(0),step.evidence_effects.unsqueeze(0),step.evidence_meta.unsqueeze(0))
                    for a in torch.nonzero(step.predict_mask,as_tuple=False).flatten().tolist():
                        err=float((out['predicted_effect'][0,a]-step.target_effects[a]).pow(2).mean());hidden.append(out['hidden'][0,a].detach().cpu());meta.append(step.evidence_meta[a].detach().cpu());safe.append(float(err<=ACCEPTABLE_MSE));mse.append(err);family.append(fam)
    return torch.stack(hidden),torch.stack(meta),torch.tensor(safe,dtype=torch.float32),torch.tensor(mse,dtype=torch.float32),family

def _bce(model,h,y):
    model.eval()
    with torch.no_grad():return float(F.binary_cross_entropy_with_logits(model.conditional_law_confidence_head(h).squeeze(-1),y).item())
def main():
    torch.manual_seed(SEED);random.seed(SEED);torch.set_num_threads(4);root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';parent=root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt';output=root/'checkpoints/Nolane-R1.8-CCSM-CertifiedLaw.pt';result_path=root/'results/r1_8_reliability_v2.json';result_path.parent.mkdir(parents=True,exist_ok=True)
    model,parent_meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16);fit_h,fit_m,fit_y,fit_err,fit_f=_cache(model,FIT_START,FIT_COUNT);val_h,val_m,val_y,val_err,val_f=_cache(model,VAL_START,VAL_COUNT);names=set(configure_reliability_training(model));params=[p for p in model.parameters() if p.requires_grad];assert sum(p.numel() for p in params)==257;optimizer=torch.optim.AdamW(params,lr=LR,weight_decay=WEIGHT_DECAY);best_bce=_bce(model,val_h,val_y);initial_bce=best_bce;best_epoch=0;best_state={n:p.detach().cpu().clone() for n,p in model.named_parameters() if n in names};history=[]
    for epoch in range(1,EPOCHS+1):
        model.train();order=torch.randperm(len(fit_h));total=0.;batches=0
        for start in range(0,len(order),BATCH_SIZE):
            idx=order[start:start+BATCH_SIZE];optimizer.zero_grad(set_to_none=True);logits=model.conditional_law_confidence_head(fit_h[idx]).squeeze(-1);loss=F.binary_cross_entropy_with_logits(logits,fit_y[idx]);loss.backward();optimizer.step();total+=float(loss.detach());batches+=1
        val_bce=_bce(model,val_h,val_y);history.append({'epoch':epoch,'train_bce':total/max(1,batches),'val_bce':val_bce})
        if val_bce<best_bce:best_bce=val_bce;best_epoch=epoch;best_state={n:p.detach().cpu().clone() for n,p in model.named_parameters() if n in names}
    named=dict(model.named_parameters())
    with torch.no_grad():
        for n,v in best_state.items():named[n].copy_(v)
        conf=torch.sigmoid(model.conditional_law_confidence_head(val_h).squeeze(-1));score=learned_certificate_scores(conf[:,None],val_m[:,None,:]).squeeze(1)
    rows=[ReliabilityTrainingRow(val_f[i],float(score[i]),float(val_err[i])) for i in range(len(val_h))]
    try:gate=calibrate_learned_certificate(rows,thresholds=THRESHOLDS,acceptable_mse=ACCEPTABLE_MSE,required_precision=REQUIRED_PRECISION,min_coverage=MIN_COVERAGE,min_family_coverage=MIN_FAMILY_COVERAGE);accepted=True
    except RuntimeError:gate=None;accepted=False
    protocol={'fit_indices':[FIT_START,FIT_START+FIT_COUNT],'val_indices':[VAL_START,VAL_START+VAL_COUNT],'families':list(R18_FAMILIES),'seed':SEED,'epochs':EPOCHS,'lr':LR,'weight_decay':WEIGHT_DECAY,'batch_size':BATCH_SIZE,'thresholds':list(THRESHOLDS),'acceptable_mse':ACCEPTABLE_MSE,'required_precision':REQUIRED_PRECISION,'min_coverage':MIN_COVERAGE,'min_family_coverage':MIN_FAMILY_COVERAGE};report={'version':'r1.8-reliability-v2','parent_sha256':sha256_file(parent),'parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],'protocol':protocol,'fit_rows':len(fit_h),'val_rows':len(val_h),'initial_val_bce':initial_bce,'best_epoch':best_epoch,'best_val_bce':best_bce,'accepted_for_active_control':accepted,'gate':(gate.__dict__ if gate else None),'history':history};result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not accepted:print(json.dumps({'accepted':False,'best_epoch':best_epoch,'best_val_bce':best_bce},sort_keys=True));raise SystemExit(2)
    meta=save_r17_checkpoint(output,model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'r1.8-learned-reliability-v2','conditional_law_parent_sha256':sha256_file(parent),'protocol':protocol,'gate':gate.__dict__});report['checkpoint']=checkpoint_metadata_for_report(meta);result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({'accepted':True,'best_epoch':best_epoch,'best_val_bce':best_bce,'gate':gate.__dict__,'checkpoint':report['checkpoint']},sort_keys=True))
if __name__=='__main__':main()
