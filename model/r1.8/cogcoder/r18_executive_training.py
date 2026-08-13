from __future__ import annotations

import copy
from dataclasses import dataclass

import torch
from torch import Tensor

from .neural_system2 import NeuralSystem2Workspace, encode_action_descriptions, encode_structured_observation, structured_numeric_delta_sketch
from .r18_benchmark import R18Task, oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint
from .r18_training import _public_state, _safe_exploration_action

@dataclass(frozen=True)
class ExecutiveTrainingStep:
    state_sketch: Tensor; context_fingerprint: Tensor; progress: Tensor; budget_fraction: Tensor; previous_feedback: Tensor; conditional_hidden: Tensor; control_effect: Tensor; evidence_meta: Tensor; progress_memory: Tensor; label: int
@dataclass(frozen=True)
class ExecutiveTrainingEpisode:
    task_id: str; family: str; steps: tuple[ExecutiveTrainingStep, ...]

def executive_trainable_parameter_names(model: NeuralSystem2Workspace) -> list[str]:
    names=[name for name,_ in model.named_parameters() if name.startswith('r18_executive_')]
    if not names: raise ValueError('model exposes no r18_executive_ parameters')
    return names
def configure_executive_training(model: NeuralSystem2Workspace) -> list[str]:
    names=executive_trainable_parameter_names(model); allowed=set(names)
    for name,parameter in model.named_parameters(): parameter.requires_grad_(name in allowed)
    return names
def _context_key(context: Tensor) -> bytes: return context.detach().cpu().contiguous().numpy().tobytes()
def _context_progress_rows(store,key,action_count):
    if key not in store: store[key]=[[0.0,0.0] for _ in range(action_count)]
    return store[key]
def _context_counts(store,key,action_count):
    if key not in store: store[key]=[0 for _ in range(action_count)]
    return store[key]
def collect_executive_episode(model: NeuralSystem2Workspace,task:R18Task,*,max_steps:int=16)->ExecutiveTrainingEpisode:
    if task.split!='train': raise ValueError('executive collector only accepts train split tasks')
    if max_steps<1: raise ValueError('max_steps must be positive')
    model.eval(); action_tokens=encode_action_descriptions(task.action_descriptions,max_bytes=64).unsqueeze(0)
    with torch.no_grad(): action_embeddings=model.action_encoder(action_tokens)[0].detach().cpu()
    action_count=int(action_embeddings.shape[0]); non_submit=[i for i,d in enumerate(task.action_descriptions) if 'submit' not in d.lower()]; evidence_memory=ConditionalEvidenceMemory(action_count=action_count,effect_dim=model.psr_sketch_dim); progress_by_context={}; counts_by_context={}; previous_feedback=torch.zeros(3,dtype=torch.float32); initial_budget=max(1.0,float(task.observe()['budget_remaining'])); rows=[]
    for _ in range(max_steps):
        if task.done: break
        observation=task.observe(); before_text=task.render_observation(); before_ids,before_values,state_sketch=_public_state(before_text,sketch_dim=model.psr_sketch_dim); context=public_context_fingerprint(before_text,dims=model.conditional_law_context_dim); key=_context_key(context); progress_rows=_context_progress_rows(progress_by_context,key,action_count); local_counts=_context_counts(counts_by_context,key,action_count); evidence_rows=[]; meta_rows=[]
        for action_index in range(action_count):
            lookup=evidence_memory.retrieve(action_index,context); evidence_rows.append(lookup.effect); meta_rows.append(torch.tensor([min(1.0,lookup.count/4.0),lookup.consistency,lookup.context_similarity],dtype=torch.float32))
        evidence_effects=torch.stack(evidence_rows); evidence_meta=torch.stack(meta_rows); progress_memory=torch.tensor([[float(delta),min(1.0,float(count)/4.0)] for delta,count in progress_rows],dtype=torch.float32)
        with torch.no_grad():
            law=model.conditional_law_scores(state_sketch.unsqueeze(0),context.unsqueeze(0),action_embeddings.unsqueeze(0),evidence_effects.unsqueeze(0),evidence_meta.unsqueeze(0)); conditional_hidden=law['hidden'][0].detach().cpu(); control_effect=model.conditional_control_effect_scores(conditional_hidden.unsqueeze(0))[0].detach().cpu()
        unexplored=[i for i in non_submit if local_counts[i]==0]; label=_safe_exploration_action(task,unexplored,local_counts) if unexplored else int(oracle_plan(copy.deepcopy(task))[0])
        rows.append(ExecutiveTrainingStep(state_sketch.detach().cpu(),context.detach().cpu(),torch.tensor([float(observation['progress_signal'])],dtype=torch.float32),torch.tensor([float(observation['budget_remaining'])/initial_budget],dtype=torch.float32),previous_feedback.detach().clone(),conditional_hidden,control_effect,evidence_meta.detach().cpu(),progress_memory,int(label)))
        result=task.step(label); after_ids,after_values=encode_structured_observation(task.render_observation(),max_atoms=96); observed_effect=structured_numeric_delta_sketch(before_ids,before_values,after_ids.unsqueeze(0),after_values.unsqueeze(0),sketch_dim=model.psr_sketch_dim).squeeze(0).detach().cpu(); evidence_memory.update(label,context,state_sketch,observed_effect); local_counts[label]+=1; progress_rows[label][0]=float(result.progress_delta); progress_rows[label][1]+=1.0; previous_feedback=torch.tensor([float(result.progress_delta),float(result.information_gain),float(result.failed)],dtype=torch.float32)
    return ExecutiveTrainingEpisode(task.task_id,task.family,tuple(rows))

def _executive_forward_step(model,step,recurrent_state):
    return model.r18_executive_step(state_sketch=step.state_sketch.unsqueeze(0),context_fingerprint=step.context_fingerprint.unsqueeze(0),progress=step.progress.unsqueeze(0),budget_fraction=step.budget_fraction.unsqueeze(0),previous_feedback=step.previous_feedback.unsqueeze(0),conditional_hidden=step.conditional_hidden.unsqueeze(0),control_effect=step.control_effect.unsqueeze(0),evidence_meta=step.evidence_meta.unsqueeze(0),progress_memory=step.progress_memory.unsqueeze(0),recurrent_state=recurrent_state)
def evaluate_executive_episodes(model,episodes,*,reset_state_each_step:bool=False)->dict[str,object]:
    import torch.nn.functional as F
    from collections import defaultdict
    model.eval();total_loss=0.0;total_correct=0;total_steps=0;family=defaultdict(lambda:{'loss':0.0,'correct':0,'steps':0})
    with torch.no_grad():
        for episode in episodes:
            recurrent=model.init_r18_executive_state(batch_size=1)
            for step in episode.steps:
                if reset_state_each_step: recurrent=model.init_r18_executive_state(batch_size=1)
                out=_executive_forward_step(model,step,recurrent);logits=out['logits'];label=torch.tensor([int(step.label)],dtype=torch.long);loss=F.cross_entropy(logits,label);prediction=int(logits.argmax(dim=-1));correct=int(prediction==int(step.label));total_loss+=float(loss);total_correct+=correct;total_steps+=1;slot=family[episode.family];slot['loss']+=float(loss);slot['correct']+=correct;slot['steps']+=1;recurrent=out['state']
    families={name:{'cross_entropy':row['loss']/max(1,row['steps']),'accuracy':row['correct']/max(1,row['steps']),'steps':row['steps']} for name,row in sorted(family.items())}
    return {'cross_entropy':total_loss/max(1,total_steps),'accuracy':total_correct/max(1,total_steps),'steps':total_steps,'families':families}
def train_executive_epoch(model,episodes,optimizer)->float:
    import torch.nn.functional as F
    model.train();order=torch.randperm(len(episodes)).tolist();total_loss=0.0;updates=0
    for episode_index in order:
        episode=episodes[episode_index]
        if not episode.steps: continue
        optimizer.zero_grad(set_to_none=True);recurrent=model.init_r18_executive_state(batch_size=1);losses=[]
        for step in episode.steps:
            out=_executive_forward_step(model,step,recurrent);label=torch.tensor([int(step.label)],dtype=torch.long);losses.append(F.cross_entropy(out['logits'],label));recurrent=out['state']
        loss=torch.stack(losses).mean();loss.backward();params=[p for p in model.parameters() if p.requires_grad]
        if params: torch.nn.utils.clip_grad_norm_(params,1.0)
        optimizer.step();total_loss+=float(loss.detach());updates+=1
    return total_loss/max(1,updates)
