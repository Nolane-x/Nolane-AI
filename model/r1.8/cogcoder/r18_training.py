from __future__ import annotations

import copy
from dataclasses import dataclass

import torch
from torch import Tensor

from .neural_system2 import NeuralSystem2Workspace, encode_action_descriptions, encode_structured_observation, structured_numeric_delta_sketch, structured_numeric_state_sketch
from .r18_benchmark import R18Task, oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint

@dataclass(frozen=True)
class ConditionalLawTrainingStep:
    state_sketch: Tensor; context_fingerprint: Tensor; action_embeddings: Tensor; evidence_effects: Tensor; evidence_meta: Tensor; target_effects: Tensor; predict_mask: Tensor; executed_action: int; observed_effect: Tensor

@dataclass(frozen=True)
class ConditionalLawEpisode:
    task_id: str; family: str; steps: tuple[ConditionalLawTrainingStep, ...]

def conditional_law_trainable_parameter_names(model: NeuralSystem2Workspace) -> list[str]:
    names=[name for name,_ in model.named_parameters() if name.startswith('conditional_law_')]
    if not names: raise ValueError('model exposes no conditional_law_ parameters')
    return names

def configure_conditional_law_training(model: NeuralSystem2Workspace) -> list[str]:
    """Freeze the entire parent and expose only R1.8 conditional-law parameters."""
    names=conditional_law_trainable_parameter_names(model); allowed=set(names)
    for name,parameter in model.named_parameters(): parameter.requires_grad_(name in allowed)
    return names

def _public_state(text:str,*,sketch_dim:int)->tuple[Tensor,Tensor,Tensor]:
    ids,values=encode_structured_observation(text,max_atoms=96); ids_b=ids.unsqueeze(0); values_b=values.unsqueeze(0); state=structured_numeric_state_sketch(ids_b,values_b,sketch_dim=sketch_dim); return ids_b,values_b,state.squeeze(0)
def _counterfactual_effects(task:R18Task,before_ids:Tensor,before_values:Tensor,action_count:int,sketch_dim:int)->Tensor:
    rows=[]
    for action_index in range(action_count):
        branch=copy.deepcopy(task); result=branch.step(action_index); after_ids,after_values=encode_structured_observation(result.observation and branch.render_observation(),max_atoms=96); rows.append(structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=sketch_dim).squeeze(0))
    return torch.stack(rows)
def _safe_exploration_action(task:R18Task,actions:list[int],counts:list[int])->int:
    for action_index in sorted(actions,key=lambda index:(counts[index],index)):
        branch=copy.deepcopy(task); result=branch.step(action_index)
        if result.done: continue
        try: oracle_plan(branch)
        except RuntimeError: continue
        return int(action_index)
    return int(oracle_plan(copy.deepcopy(task))[0])
def collect_conditional_law_episode(model:NeuralSystem2Workspace,task:R18Task,*,exploration_steps:int=6,max_steps:int=16)->ConditionalLawEpisode:
    if task.split!='train': raise ValueError('conditional-law collector only accepts train split tasks')
    if exploration_steps<0 or max_steps<1: raise ValueError('invalid exploration/max_steps')
    model.eval(); action_tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad(): action_embeddings=model.action_encoder(action_tokens)[0].detach().cpu()
    action_count=action_embeddings.shape[0]; non_submit=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()]; counts=[0]*action_count; memory=ConditionalEvidenceMemory(action_count=action_count,effect_dim=model.psr_sketch_dim); steps=[]
    while not task.done and len(steps)<max_steps:
        before_text=task.render_observation(); before_ids,before_values,state_sketch=_public_state(before_text,sketch_dim=model.psr_sketch_dim); context=public_context_fingerprint(before_text,dims=model.conditional_law_context_dim); evidence_rows=[]; meta_rows=[]
        for action_index in range(action_count):
            lookup=memory.retrieve(action_index,context); evidence_rows.append(lookup.effect); meta_rows.append(torch.tensor([min(1.0,lookup.count/4.0),lookup.consistency,lookup.context_similarity],dtype=torch.float32))
        evidence_effects=torch.stack(evidence_rows); evidence_meta=torch.stack(meta_rows); target_effects=_counterfactual_effects(task,before_ids,before_values,action_count,model.psr_sketch_dim); predict_mask=torch.tensor(['submit' not in d.lower() for d in task.action_descriptions],dtype=torch.bool)
        executed=_safe_exploration_action(task,non_submit,counts) if len(steps)<exploration_steps and non_submit else int(oracle_plan(copy.deepcopy(task))[0])
        result=task.step(executed); after_ids,after_values=encode_structured_observation(task.render_observation(),max_atoms=96); observed_effect=structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=model.psr_sketch_dim).squeeze(0).detach().cpu(); memory.update(executed,context,state_sketch,observed_effect); counts[executed]+=1
        steps.append(ConditionalLawTrainingStep(state_sketch.detach().cpu(),context.detach().cpu(),action_embeddings,evidence_effects.detach().cpu(),evidence_meta.detach().cpu(),target_effects.detach().cpu(),predict_mask,executed,observed_effect))
        if result.done: break
    return ConditionalLawEpisode(task.task_id,task.family,tuple(steps))
def _conditional_law_batches(episodes,*,batch_size:int=128):
    from collections import defaultdict
    grouped=defaultdict(list)
    for episode in episodes:
        for step in episode.steps: grouped[int(step.action_embeddings.shape[0])].append((episode.family,step))
    for action_count,rows in grouped.items():
        for start in range(0,len(rows),batch_size): yield action_count,rows[start:start+batch_size]
def evaluate_conditional_law_episodes(model:NeuralSystem2Workspace,episodes,*,batch_size:int=128)->dict[str,object]:
    from collections import defaultdict
    model.eval(); totals={'candidate_sq':0.0,'baseline_sq':0.0,'elements':0}; family_totals=defaultdict(lambda:{'candidate_sq':0.0,'baseline_sq':0.0,'elements':0})
    with torch.no_grad():
        for _,items in _conditional_law_batches(episodes,batch_size=batch_size):
            state=torch.stack([s.state_sketch for _,s in items]); context=torch.stack([s.context_fingerprint for _,s in items]); actions=torch.stack([s.action_embeddings for _,s in items]); evidence=torch.stack([s.evidence_effects for _,s in items]); meta=torch.stack([s.evidence_meta for _,s in items]); target=torch.stack([s.target_effects for _,s in items]); mask=torch.stack([s.predict_mask for _,s in items]); predicted=model.conditional_law_scores(state,context,actions,evidence,meta)['predicted_effect']
            for row_index,(family,_) in enumerate(items):
                m=mask[row_index]; pd=predicted[row_index,m]-target[row_index,m]; bd=evidence[row_index,m]-target[row_index,m]; cs=float((pd*pd).sum()); bs=float((bd*bd).sum()); n=int(pd.numel()); totals['candidate_sq']+=cs; totals['baseline_sq']+=bs; totals['elements']+=n; family_totals[family]['candidate_sq']+=cs; family_totals[family]['baseline_sq']+=bs; family_totals[family]['elements']+=n
    def summarize(row):
        d=max(1,int(row['elements'])); c=float(row['candidate_sq'])/d; b=float(row['baseline_sq'])/d; return {'candidate_mse':c,'baseline_mse':b,'relative_improvement':1.0-c/max(b,1e-12),'elements':int(row['elements'])}
    return {**summarize(totals),'families':{name:summarize(row) for name,row in sorted(family_totals.items())}}
def train_conditional_law_epoch(model:NeuralSystem2Workspace,episodes,optimizer:torch.optim.Optimizer,*,batch_size:int=128)->float:
    import torch.nn.functional as F
    model.train(); batches=list(_conditional_law_batches(episodes,batch_size=batch_size))
    if not batches:return 0.0
    total=0.0; count=0
    for batch_index in torch.randperm(len(batches)).tolist():
        _,items=batches[batch_index]; optimizer.zero_grad(set_to_none=True); state=torch.stack([s.state_sketch for _,s in items]); context=torch.stack([s.context_fingerprint for _,s in items]); actions=torch.stack([s.action_embeddings for _,s in items]); evidence=torch.stack([s.evidence_effects for _,s in items]); meta=torch.stack([s.evidence_meta for _,s in items]); target=torch.stack([s.target_effects for _,s in items]); mask=torch.stack([s.predict_mask for _,s in items]); predicted=model.conditional_law_scores(state,context,actions,evidence,meta)['predicted_effect']; loss=F.mse_loss(predicted[mask],target[mask]); loss.backward(); params=[p for p in model.parameters() if p.requires_grad]
        if params: torch.nn.utils.clip_grad_norm_(params,1.0)
        optimizer.step(); total+=float(loss.detach()); count+=1
    return total/max(1,count)
def conditional_law_internal_gate(metrics:dict[str,object])->bool:
    if not float(metrics['candidate_mse'])<float(metrics['baseline_mse']):return False
    families=metrics.get('families',{}); required={'conditional_regimes','regime_switch','implicit_goal_regimes','causal_prerequisites'}
    if not isinstance(families,dict) or set(families)!=required:return False
    return all(float(row['candidate_mse'])<=float(row['baseline_mse']) for row in families.values())
