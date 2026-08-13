from __future__ import annotations

import copy
from dataclasses import dataclass
import torch
from torch import Tensor
from .neural_system2 import NeuralSystem2Workspace,encode_action_descriptions,encode_structured_observation,structured_numeric_delta_sketch
from .r18_benchmark import R18Task,oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory,public_context_fingerprint
from .r18_training import _public_state,_safe_exploration_action

@dataclass(frozen=True)
class ExecutiveTrainingStep:
    state_sketch:Tensor;context_fingerprint:Tensor;progress:Tensor;budget_fraction:Tensor;previous_feedback:Tensor;conditional_hidden:Tensor;control_effect:Tensor;evidence_meta:Tensor;progress_memory:Tensor;label:int
@dataclass(frozen=True)
class ExecutiveTrainingEpisode:
    task_id:str;family:str;steps:tuple[ExecutiveTrainingStep,...]

def executive_trainable_parameter_names(model:NeuralSystem2Workspace)->list[str]:
    names=[name for name,_ in model.named_parameters() if name.startswith('r18_executive_')]
    if not names:raise ValueError('model exposes no r18_executive_ parameters')
    return names
def configure_executive_training(model:NeuralSystem2Workspace)->list[str]:
    names=executive_trainable_parameter_names(model);allowed=set(names)
    for name,p in model.named_parameters():p.requires_grad_(name in allowed)
    return names
def _context_key(context:Tensor)->bytes:return context.detach().cpu().contiguous().numpy().tobytes()
def _context_progress_rows(store,key,action_count):
    if key not in store:store[key]=[[0.0,0.0] for _ in range(action_count)]
    return store[key]
def _context_counts(store,key,action_count):
    if key not in store:store[key]=[0 for _ in range(action_count)]
    return store[key]
def collect_executive_episode(model:NeuralSystem2Workspace,task:R18Task,*,max_steps:int=16)->ExecutiveTrainingEpisode:
    if task.split!='train':raise ValueError('executive collector only accepts train split tasks')
    if max_steps<1:raise ValueError('max_steps must be positive')
    model.eval();tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad():actions=model.action_encoder(tokens)[0].detach().cpu()
    action_count=int(actions.shape[0]);non_submit=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()];evidence_memory=ConditionalEvidenceMemory(action_count=action_count,effect_dim=model.psr_sketch_dim);progress_by_context={};counts_by_context={};previous_feedback=torch.zeros(3);initial_budget=max(1.0,float(task.observe()['budget_remaining']));rows=[]
    for _ in range(max_steps):
        if task.done:break
        obs=task.observe();text=task.render_observation();before_ids,before_values,state=_public_state(text,sketch_dim=model.psr_sketch_dim);context=public_context_fingerprint(text,dims=model.conditional_law_context_dim);key=_context_key(context);progress_rows=_context_progress_rows(progress_by_context,key,action_count);local_counts=_context_counts(counts_by_context,key,action_count);ev=[];meta=[]
        for i in range(action_count):
            lookup=evidence_memory.retrieve(i,context);ev.append(lookup.effect);meta.append(torch.tensor([min(1.0,lookup.count/4.0),lookup.consistency,lookup.context_similarity],dtype=torch.float32))
        evidence=torch.stack(ev);evidence_meta=torch.stack(meta);progress_memory=torch.tensor([[float(delta),min(1.0,float(count)/4.0)] for delta,count in progress_rows],dtype=torch.float32)
        with torch.no_grad():
            law=model.conditional_law_scores(state.unsqueeze(0),context.unsqueeze(0),actions.unsqueeze(0),evidence.unsqueeze(0),evidence_meta.unsqueeze(0));hidden=law['hidden'][0].detach().cpu();control=model.conditional_control_effect_scores(hidden.unsqueeze(0))[0].detach().cpu()
        unexplored=[i for i in non_submit if local_counts[i]==0];label=_safe_exploration_action(task,unexplored,local_counts) if unexplored else int(oracle_plan(copy.deepcopy(task))[0])
        rows.append(ExecutiveTrainingStep(state.detach().cpu(),context.detach().cpu(),torch.tensor([float(obs['progress_signal'])]),torch.tensor([float(obs['budget_remaining'])/initial_budget]),previous_feedback.detach().clone(),hidden,control,evidence_meta.detach().cpu(),progress_memory,int(label)))
        result=task.step(label);after_ids,after_values=encode_structured_observation(task.render_observation(),max_atoms=96);observed=structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=model.psr_sketch_dim).squeeze(0).detach().cpu();evidence_memory.update(label,context,state,observed);local_counts[label]+=1;progress_rows[label][0]=float(result.progress_delta);progress_rows[label][1]+=1.0;previous_feedback=torch.tensor([float(result.progress_delta),float(result.information_gain),float(result.failed)])
    return ExecutiveTrainingEpisode(task.task_id,task.family,tuple(rows))
