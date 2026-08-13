from __future__ import annotations
import copy
from dataclasses import dataclass
import torch
from torch import Tensor
from .neural_system2 import NeuralSystem2Workspace,encode_action_descriptions,encode_structured_observation,project_causal_role_effects,structured_numeric_delta_sketch
from .r18_benchmark import R18Task,oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory,public_context_fingerprint
from .r18_control_effect_training import _counterfactual_structured_effects,_public_state,_safe_exploration_action
from .r18_control_state import infer_controllable_effect_projection

@dataclass(frozen=True)
class NonlinearReliabilityRow:
    family:str;features:Tensor;prediction_mse:float;safe:float;seen:float

def nonlinear_reliability_trainable_parameter_names(model:NeuralSystem2Workspace)->list[str]:
    names=[n for n,_ in model.named_parameters() if n.startswith('conditional_reliability_head.')]
    if not names:raise ValueError('model exposes no conditional_reliability_head parameters')
    return names

def configure_nonlinear_reliability_training(model:NeuralSystem2Workspace)->list[str]:
    names=nonlinear_reliability_trainable_parameter_names(model);allowed=set(names)
    for name,p in model.named_parameters():p.requires_grad_(name in allowed)
    return names

def collect_nonlinear_reliability_rows(model:NeuralSystem2Workspace,task:R18Task,*,safe_mse:float,exploration_steps:int=6,max_steps:int=16)->list[NonlinearReliabilityRow]:
    if task.split!='train':raise ValueError('nonlinear-reliability collector only accepts train split tasks')
    if safe_mse<=0:raise ValueError('safe_mse must be positive')
    model.eval();tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad():actions=model.action_encoder(tokens)[0].detach().cpu()
    action_count=int(actions.shape[0]);non_submit=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()];counts=[0]*action_count;memory=ConditionalEvidenceMemory(action_count=action_count,effect_dim=model.psr_sketch_dim);projection=None;rows=[]
    while not task.done and sum(counts)<max_steps:
        text=task.render_observation();before_ids,before_values,state=_public_state(text,sketch_dim=model.psr_sketch_dim);context=public_context_fingerprint(text,dims=model.conditional_law_context_dim);ev=[];meta=[]
        for i in range(action_count):
            lookup=memory.retrieve(i,context);ev.append(lookup.effect);meta.append(torch.tensor([min(1.,lookup.count/4.),lookup.consistency,lookup.context_similarity]))
        evidence=torch.stack(ev);evidence_meta=torch.stack(meta);targets=_counterfactual_structured_effects(task,before_ids,before_values,action_count,model.psr_sketch_dim)
        with torch.no_grad():law=model.conditional_law_scores(state.unsqueeze(0),context.unsqueeze(0),actions.unsqueeze(0),evidence.unsqueeze(0),evidence_meta.unsqueeze(0));hidden=law['hidden'][0].detach().cpu();pred=model.conditional_control_effect_scores(hidden.unsqueeze(0))[0].detach().cpu()
        executed=_safe_exploration_action(task,non_submit,counts) if sum(counts)<exploration_steps and non_submit else int(oracle_plan(copy.deepcopy(task))[0]);result=task.step(executed);after_ids,after_values=encode_structured_observation(task.render_observation(),max_atoms=96);observed=structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=model.psr_sketch_dim).squeeze(0).detach().cpu();inferred=infer_controllable_effect_projection(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),role_dim=64,source_dim=model.psr_sketch_dim)
        if float(inferred['confidence'][0])>.5:projection=inferred['effect_projection'].detach().cpu()
        if projection is not None:
            target_control=project_causal_role_effects(targets.unsqueeze(0),projection)[0].detach().cpu();evidence_control=project_causal_role_effects(evidence.unsqueeze(0),projection)[0].detach().cpu()
            with torch.no_grad():features=model.conditional_reliability_scores(hidden.unsqueeze(0),pred.unsqueeze(0),evidence_control.unsqueeze(0),evidence_meta.unsqueeze(0))['features'][0].detach().cpu()
            for i in non_submit:
                error=float((pred[i]-target_control[i]).pow(2).mean());rows.append(NonlinearReliabilityRow(task.family,features[i].clone(),error,float(error<=safe_mse),float(evidence_meta[i,0]>0)))
        memory.update(executed,context,state,observed);counts[executed]+=1
        if result.done:break
    return rows
