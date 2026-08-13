from __future__ import annotations

import copy
from dataclasses import dataclass

import torch
from torch import Tensor

from .neural_system2 import NeuralSystem2Workspace, encode_action_descriptions, encode_structured_observation, project_causal_role_effects, structured_numeric_delta_sketch
from .r18_benchmark import R18Task, oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint
from .r18_control_effect_training import _counterfactual_structured_effects, _public_state, _safe_exploration_action
from .r18_control_state import infer_controllable_effect_projection
from .r18_reliability_training import configure_reliability_training

@dataclass(frozen=True)
class ControlReliabilityRow:
    family:str; hidden:Tensor; evidence_meta:Tensor; prediction_mse:float; safe:float

def configure_control_reliability_training(model:NeuralSystem2Workspace)->list[str]: return configure_reliability_training(model)

def collect_control_reliability_rows(model:NeuralSystem2Workspace,task:R18Task,*,safe_mse:float,exploration_steps:int=6,max_steps:int=16)->list[ControlReliabilityRow]:
    if task.split!='train': raise ValueError('control-reliability collector only accepts train split tasks')
    if safe_mse<=0: raise ValueError('safe_mse must be positive')
    if exploration_steps<0 or max_steps<1: raise ValueError('invalid exploration/max_steps')
    model.eval(); action_tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad(): action_embeddings=model.action_encoder(action_tokens)[0].detach().cpu()
    action_count=int(action_embeddings.shape[0]); non_submit=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()]; counts=[0]*action_count; memory=ConditionalEvidenceMemory(action_count=action_count,effect_dim=model.psr_sketch_dim); projection=None; rows=[]
    while not task.done and sum(counts)<max_steps:
        before_text=task.render_observation(); before_ids,before_values,state_sketch=_public_state(before_text,sketch_dim=model.psr_sketch_dim); context=public_context_fingerprint(before_text,dims=model.conditional_law_context_dim); evidence_rows=[];meta_rows=[]
        for action_index in range(action_count):
            lookup=memory.retrieve(action_index,context); evidence_rows.append(lookup.effect); meta_rows.append(torch.tensor([min(1.0,lookup.count/4.0),lookup.consistency,lookup.context_similarity],dtype=torch.float32))
        evidence_effects=torch.stack(evidence_rows); evidence_meta=torch.stack(meta_rows); target_structured=_counterfactual_structured_effects(task,before_ids,before_values,action_count,model.psr_sketch_dim)
        with torch.no_grad():
            law=model.conditional_law_scores(state_sketch.unsqueeze(0),context.unsqueeze(0),action_embeddings.unsqueeze(0),evidence_effects.unsqueeze(0),evidence_meta.unsqueeze(0)); hidden=law['hidden'][0].detach().cpu(); predicted_control=model.conditional_control_effect_scores(hidden.unsqueeze(0))[0].detach().cpu()
        executed=_safe_exploration_action(task,non_submit,counts) if sum(counts)<exploration_steps and non_submit else int(oracle_plan(copy.deepcopy(task))[0]); result=task.step(executed); after_ids,after_values=encode_structured_observation(task.render_observation(),max_atoms=96); observed_structured=structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=model.psr_sketch_dim).squeeze(0).detach().cpu(); inferred=infer_controllable_effect_projection(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),role_dim=64,source_dim=model.psr_sketch_dim)
        if float(inferred['confidence'][0])>.5: projection=inferred['effect_projection'].detach().cpu()
        if projection is not None:
            target_control=project_causal_role_effects(target_structured.unsqueeze(0),projection)[0].detach().cpu()
            for action_index in non_submit:
                error=float((predicted_control[action_index]-target_control[action_index]).pow(2).mean()); rows.append(ControlReliabilityRow(task.family,hidden[action_index].clone(),evidence_meta[action_index].clone(),error,float(error<=safe_mse)))
        memory.update(executed,context,state_sketch,observed_structured);counts[executed]+=1
        if result.done: break
    return rows
