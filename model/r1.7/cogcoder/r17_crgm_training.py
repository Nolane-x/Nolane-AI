from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

from .neural_system2 import (
    NeuralSystem2Workspace,
    encode_action_descriptions,
    encode_structured_observation,
    infer_causal_numeric_roles,
    structured_numeric_delta_sketch,
    structured_numeric_state_sketch,
)
from .r17_benchmark import R17Task, oracle_plan


@dataclass(frozen=True)
class CRGMTrainingStep:
    need_sketch: Tensor
    role_confidence: Tensor
    retrieved_law: Tensor
    law_confidence: Tensor
    target_progress: Tensor
    baseline_progress: Tensor
    predict_mask: Tensor


@dataclass(frozen=True)
class CRGMEpisode:
    task_id: str
    family: str
    steps: tuple[CRGMTrainingStep, ...]


def crgm_trainable_parameter_names(model: NeuralSystem2Workspace, *, include_policy_scale: bool = False) -> list[str]:
    names=[]
    for name,_ in model.named_parameters():
        if not name.startswith('causal_role_goal_'): continue
        if not include_policy_scale and name=='causal_role_goal_policy_scale': continue
        names.append(name)
    if not names: raise ValueError('model exposes no causal_role_goal_ parameters')
    return names


def _structured(model,task):
    ids,values=encode_structured_observation(task.render_observation(),max_atoms=96); ids_b=ids.unsqueeze(0); values_b=values.unsqueeze(0)
    with torch.no_grad():
        atoms,mask=model.structured_observation_encoder.encode_atoms(ids_b,values_b)
        state=structured_numeric_state_sketch(ids_b,values_b,sketch_dim=model.psr_sketch_dim)
    return ids_b,values_b,atoms,mask,state


def _counterfactual_progress(task,action_index):
    branch=copy.deepcopy(task); return float(branch.step(int(action_index)).progress_delta)


def _safe_exploration_action(task,non_submit,observed_counts):
    for action_index in sorted(non_submit,key=lambda i:(observed_counts[i],i)):
        branch=copy.deepcopy(task); result=branch.step(action_index)
        if result.done: continue
        try: oracle_plan(branch)
        except RuntimeError: continue
        return int(action_index)
    return int(oracle_plan(copy.deepcopy(task))[0])


def collect_crgm_episode(model:NeuralSystem2Workspace,task:R17Task,*,exploration_steps:int=6,max_steps:int=14)->CRGMEpisode:
    if task.split!='train': raise ValueError('CRGM training collector only accepts train split tasks')
    if task.family not in {'causal_laws','causal_switch'}: raise ValueError('CRGM world-model collector requires a causal FIGG family')
    model.eval(); action_tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad(): action_embeddings=model.action_encoder(action_tokens).detach()
    action_count=action_embeddings.shape[1]; non_submit=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()]; observed_counts=[0]*action_count
    law_state=model.init_causal_law_state(batch_size=1,device=torch.device('cpu'))
    previous_ids,previous_values,_,_,previous_state=_structured(model,task); rows=[]
    for transition_index in range(max_steps):
        if task.done: break
        executed=_safe_exploration_action(task,non_submit,observed_counts) if transition_index<exploration_steps and non_submit else int(oracle_plan(copy.deepcopy(task))[0])
        result=task.step(executed); observed_counts[executed]+=1
        if result.done: break
        current_ids,current_values,atoms,atom_mask,current_state=_structured(model,task)
        observed_delta=structured_numeric_delta_sketch(previous_ids,previous_values,current_ids,current_values,sketch_dim=model.psr_sketch_dim)
        with torch.no_grad():
            law_state=model.update_causal_laws(previous_state,action_embeddings,executed,observed_delta,law_state)
            role=infer_causal_numeric_roles(previous_ids,previous_values,current_ids,current_values,sketch_dim=model.causal_role_goal_need_dim)
            law_scores=model.causal_law_scores(current_state,action_embeddings,law_state)
            baseline=model.goal_difference_scores(atoms,atom_mask,law_scores['predicted_delta'],action_embeddings,law_scores['confidence'])['predicted_progress']
        target=torch.tensor([_counterfactual_progress(task,i) for i in range(action_count)],dtype=torch.float32)
        legal=torch.tensor(['submit' not in d.lower() for d in task.action_descriptions],dtype=torch.bool)
        predict_mask=legal & law_scores['confidence'][0].detach().cpu().gt(1e-6)
        if float(role['confidence'][0])<=0: predict_mask=torch.zeros_like(predict_mask)
        if bool(predict_mask.any().item()):
            rows.append(CRGMTrainingStep(role['need_sketch'][0].detach().cpu(),role['confidence'][0].detach().cpu(),law_scores['retrieved_law'][0].detach().cpu(),law_scores['confidence'][0].detach().cpu(),target,baseline[0].detach().cpu(),predict_mask))
        previous_ids,previous_values,previous_state=current_ids,current_values,current_state
    return CRGMEpisode(task.task_id,task.family,tuple(rows))


def _ranking_correct(prediction,target,mask):
    chosen=int(prediction.masked_fill(~mask,float('-inf')).argmax().item()); best=float(target[mask].max().item()); return float(target[chosen].item())>=best-1e-6


def evaluate_crgm_episodes(model,episodes):
    model.eval(); csq=bsq=0.0; elements=cr=br=rows=0; family=defaultdict(lambda:{'candidate_sq':0.0,'baseline_sq':0.0,'elements':0,'candidate_rank':0,'baseline_rank':0,'rows':0})
    with torch.no_grad():
        for episode in episodes:
            for step in episode.steps:
                pred=model.causal_role_goal_scores(step.need_sketch.unsqueeze(0),step.role_confidence.reshape(1),step.retrieved_law.unsqueeze(0),step.law_confidence.unsqueeze(0))['predicted_progress'][0]; mask=step.predict_mask
                diff=pred[mask]-step.target_progress[mask]; bdiff=step.baseline_progress[mask]-step.target_progress[mask]; c=float((diff*diff).sum()); b=float((bdiff*bdiff).sum()); n=int(diff.numel()); co=_ranking_correct(pred,step.target_progress,mask); bo=_ranking_correct(step.baseline_progress,step.target_progress,mask)
                csq+=c; bsq+=b; elements+=n; cr+=int(co); br+=int(bo); rows+=1; r=family[episode.family]; r['candidate_sq']+=c; r['baseline_sq']+=b; r['elements']+=n; r['candidate_rank']+=int(co); r['baseline_rank']+=int(bo); r['rows']+=1
    families={}
    for name,r in family.items():
        en=max(1,int(r['elements'])); rn=max(1,int(r['rows'])); families[name]={'candidate_mse':float(r['candidate_sq'])/en,'baseline_mse':float(r['baseline_sq'])/en,'candidate_rank_accuracy':int(r['candidate_rank'])/rn,'baseline_rank_accuracy':int(r['baseline_rank'])/rn,'elements':int(r['elements']),'rows':int(r['rows'])}
    return {'candidate_mse':csq/max(1,elements),'baseline_mse':bsq/max(1,elements),'candidate_rank_accuracy':cr/max(1,rows),'baseline_rank_accuracy':br/max(1,rows),'elements':elements,'rows':rows,'families':families}


def train_crgm_epoch(model,episodes,optimizer):
    model.train(); total=0.0; count=0
    for episode in episodes:
        optimizer.zero_grad(set_to_none=True); loss=torch.zeros((),dtype=torch.float32); terms=0
        for step in episode.steps:
            pred=model.causal_role_goal_scores(step.need_sketch.unsqueeze(0),step.role_confidence.reshape(1),step.retrieved_law.unsqueeze(0),step.law_confidence.unsqueeze(0))['predicted_progress'][0]; mask=step.predict_mask; loss=loss+F.mse_loss(pred[mask],step.target_progress[mask]); terms+=1
        if not terms: continue
        loss=loss/terms; loss.backward(); params=[p for p in model.parameters() if p.requires_grad];
        if params: torch.nn.utils.clip_grad_norm_(params,1.0)
        optimizer.step(); total+=float(loss.detach()); count+=1
    return total/max(1,count)


def crgm_internal_gate(metrics):
    if not float(metrics['candidate_mse'])<float(metrics['baseline_mse']): return False
    if not float(metrics['candidate_rank_accuracy'])>float(metrics['baseline_rank_accuracy']): return False
    families=metrics.get('families',{})
    for name in ('causal_laws','causal_switch'):
        row=families.get(name)
        if not isinstance(row,dict) or float(row['candidate_rank_accuracy'])<float(row['baseline_rank_accuracy']): return False
    return True
