from __future__ import annotations
import argparse,copy,json
from pathlib import Path
import torch
from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_role_effect_training import collect_role_effect_episode,evaluate_role_effect_episodes,role_effect_internal_gate,role_effect_ranker_trainable_parameter_names,train_role_effect_epoch
from cogcoder.r17_training import load_r17_checkpoint,save_r17_checkpoint,checkpoint_metadata_for_report,sha256_file
FAMILIES=('causal_laws','causal_switch')
def collect(model,start,count,explore,max_steps): return [collect_role_effect_episode(model,make_r17_task(f,'train',i),exploration_steps=explore,max_steps=max_steps) for f in FAMILIES for i in range(start,start+count)]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--fit-start',type=int,default=194);ap.add_argument('--fit-count',type=int,default=16);ap.add_argument('--val-start',type=int,default=210);ap.add_argument('--val-count',type=int,default=8);ap.add_argument('--epochs',type=int,default=60);ap.add_argument('--lr',type=float,default=1e-3);ap.add_argument('--seed',type=int,default=170717);ap.add_argument('--exploration-steps',type=int,default=6);ap.add_argument('--max-steps',type=int,default=14);args=ap.parse_args()
 torch.manual_seed(args.seed);torch.set_num_threads(1);root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';parent=root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt';model,meta=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16)
 names=set(role_effect_ranker_trainable_parameter_names(model));params=[]
 for n,p in model.named_parameters():p.requires_grad_(n in names);params.append(p) if n in names else None
 opt=torch.optim.AdamW(params,lr=args.lr,weight_decay=1e-4);fit=collect(model,args.fit_start,args.fit_count,args.exploration_steps,args.max_steps);val=collect(model,args.val_start,args.val_count,args.exploration_steps,args.max_steps);initial=evaluate_role_effect_episodes(model,val);best=initial;best_epoch=0;best_state=copy.deepcopy(model.state_dict());history=[]
 print(json.dumps({'event':'precompute','fit_steps':sum(len(e.steps) for e in fit),'val_steps':sum(len(e.steps) for e in val),'initial':initial},sort_keys=True),flush=True)
 for epoch in range(1,args.epochs+1):
  loss=train_role_effect_epoch(model,fit,opt);metrics=evaluate_role_effect_episodes(model,val);history.append({'epoch':epoch,'train_loss':loss,**metrics});print(json.dumps({'epoch':epoch,'train_loss':loss,**metrics},sort_keys=True),flush=True)
  if role_effect_internal_gate(metrics) and (best_epoch==0 or metrics['candidate_rank_accuracy']>best['candidate_rank_accuracy']):best=metrics;best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
 model.load_state_dict(best_state);accepted=best_epoch>0 and role_effect_internal_gate(best);report={'version':'r1.7-role-effect-ranker-internal-v1','protocol':vars(args),'parent_sha256':sha256_file(parent),'parent_candidate_effective_parameters':meta['candidate_effective_parameters'],'trainable_parameters':sum(p.numel() for p in params),'best_epoch':best_epoch,'initial_validation':initial,'best_validation':best,'accepted_for_policy_integration':accepted,'history':history};rp=root/'results/r1_7_role_effect_ranker_internal.json';rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 if not accepted:print(json.dumps({'accepted':False,'best_epoch':best_epoch,'best':best},sort_keys=True),flush=True);raise SystemExit(2)
 ck=save_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-RoleEffectRanker.pt',model,r1_2_checkpoint=r12,r1_6_parent_checkpoint=r16,report={'phase':'role-effect-ranker','internal_gate':best});report['checkpoint']=checkpoint_metadata_for_report(ck);rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({'accepted':True,'best_epoch':best_epoch,'best':best,'checkpoint':report['checkpoint']},sort_keys=True),flush=True)
if __name__=='__main__':main()
