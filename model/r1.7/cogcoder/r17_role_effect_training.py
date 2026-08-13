from __future__ import annotations
import copy
from collections import defaultdict
from dataclasses import dataclass
import torch
from torch import Tensor
from .neural_system2 import NeuralSystem2Workspace, encode_action_descriptions, infer_causal_numeric_roles, project_causal_role_effects, structured_numeric_delta_sketch
from .r17_benchmark import R17Task, oracle_plan
from .r17_crgm_training import _structured, _safe_exploration_action, _counterfactual_progress, _ranking_correct

@dataclass(frozen=True)
class RoleEffectStep:
    need_sketch: Tensor
    role_confidence: Tensor
    role_effects: Tensor
    law_confidence: Tensor
    target_progress: Tensor
    baseline_progress: Tensor
    predict_mask: Tensor
    best_mask: Tensor
@dataclass(frozen=True)
class RoleEffectEpisode:
    task_id:str; family:str; steps:tuple[RoleEffectStep,...]

def role_effect_ranker_trainable_parameter_names(model:NeuralSystem2Workspace)->list[str]:
    names=[name for name,_ in model.named_parameters() if name.startswith('causal_role_effect_ranker.')]
    if not names: raise ValueError('model exposes no causal_role_effect_ranker parameters')
    return names

def role_effect_internal_gate(metrics:dict[str,object])->bool:
    if not float(metrics['candidate_rank_accuracy'])>float(metrics['baseline_rank_accuracy']): return False
    families=metrics.get('families',{})
    for name in ('causal_laws','causal_switch'):
        row=families.get(name)
        if not isinstance(row,dict) or float(row['candidate_rank_accuracy'])<float(row['baseline_rank_accuracy']): return False
    return True

def collect_role_effect_episode(model:NeuralSystem2Workspace,task:R17Task,*,exploration_steps:int=6,max_steps:int=14)->RoleEffectEpisode:
    if task.split!='train': raise ValueError('Role-Effect training collector only accepts train split tasks')
    if task.family not in {'causal_laws','causal_switch'}: raise ValueError('Role-Effect collector requires causal family')
    model.eval(); actions=model.action_encoder(encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)).detach(); count=actions.shape[1]
    non=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()]; counts=[0]*count; law=model.init_causal_law_state(batch_size=1,device=torch.device('cpu')); pids,pvals,_,_,pstate=_structured(model,task); rows=[]
    for t in range(max_steps):
        if task.done: break
        executed=_safe_exploration_action(task,non,counts) if t<exploration_steps and non else int(oracle_plan(copy.deepcopy(task))[0]); result=task.step(executed); counts[executed]+=1
        if result.done: break
        cids,cvals,atoms,mask,cstate=_structured(model,task); od=structured_numeric_delta_sketch(pids,pvals,cids,cvals,sketch_dim=model.psr_sketch_dim)
        with torch.no_grad():
            law=model.update_causal_laws(pstate,actions,executed,od,law); role=infer_causal_numeric_roles(pids,pvals,cids,cvals,sketch_dim=64,source_sketch_dim=model.psr_sketch_dim); ls=model.causal_law_scores(cstate,actions,law); effects=project_causal_role_effects(ls['predicted_delta'],role['effect_projection']); baseline=model.goal_difference_scores(atoms,mask,ls['predicted_delta'],actions,ls['confidence'])['predicted_progress']
        target=torch.tensor([_counterfactual_progress(task,i) for i in range(count)],dtype=torch.float32); legal=torch.tensor(['submit' not in d.lower() for d in task.action_descriptions],dtype=torch.bool); pm=legal & ls['confidence'][0].detach().cpu().gt(1e-6)
        if float(role['confidence'][0])<=0: pm=torch.zeros_like(pm)
        if bool(pm.any()):
            best=float(target[pm].max()); bm=pm & target.ge(best-1e-6); rows.append(RoleEffectStep(role['need_sketch'][0].detach().cpu(),role['confidence'][0].detach().cpu(),effects[0].detach().cpu(),ls['confidence'][0].detach().cpu(),target,baseline[0].detach().cpu(),pm,bm))
        pids,pvals,pstate=cids,cvals,cstate
    return RoleEffectEpisode(task.task_id,task.family,tuple(rows))

def evaluate_role_effect_episodes(model,episodes):
    model.eval(); cc=bc=rows=0; fam=defaultdict(lambda:[0,0,0])
    with torch.no_grad():
        for ep in episodes:
            for step in ep.steps:
                pred=model.causal_role_effect_rank_scores(step.need_sketch.unsqueeze(0),step.role_confidence.reshape(1),step.role_effects.unsqueeze(0),step.law_confidence.unsqueeze(0))[0]; c=_ranking_correct(pred,step.target_progress,step.predict_mask); b=_ranking_correct(step.baseline_progress,step.target_progress,step.predict_mask); cc+=int(c);bc+=int(b);rows+=1;fam[ep.family][0]+=int(c);fam[ep.family][1]+=int(b);fam[ep.family][2]+=1
    families={k:{'candidate_rank_accuracy':c/n,'baseline_rank_accuracy':b/n,'rows':n} for k,(c,b,n) in fam.items()}
    return {'candidate_rank_accuracy':cc/max(1,rows),'baseline_rank_accuracy':bc/max(1,rows),'rows':rows,'families':families}

def train_role_effect_epoch(model,episodes,optimizer):
    model.train(); total=0.0; count=0
    for ep in episodes:
        optimizer.zero_grad(set_to_none=True); loss=torch.zeros((),dtype=torch.float32); terms=0
        for step in ep.steps:
            logits=model.causal_role_effect_rank_scores(step.need_sketch.unsqueeze(0),step.role_confidence.reshape(1),step.role_effects.unsqueeze(0),step.law_confidence.unsqueeze(0))[0]; all_lse=torch.logsumexp(logits[step.predict_mask],dim=0); best_lse=torch.logsumexp(logits[step.best_mask],dim=0); loss=loss+(all_lse-best_lse);terms+=1
        if not terms: continue
        loss=loss/terms;loss.backward();params=[p for p in model.parameters() if p.requires_grad]
        if params: torch.nn.utils.clip_grad_norm_(params,1.0)
        optimizer.step();total+=float(loss.detach());count+=1
    return total/max(1,count)
