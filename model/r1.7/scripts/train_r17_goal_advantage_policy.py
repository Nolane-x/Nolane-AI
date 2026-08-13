from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import torch
import torch.nn.functional as F
from cogcoder.neural_system2 import CausalLawState, encode_structured_observation
from train_r17_causal_law_policy import _cache_rows

@dataclass
class GoalAdvantageRow:
    family: str
    base_logits: torch.Tensor
    policy_features: torch.Tensor
    confidence: torch.Tensor
    label: int

def cache_advantage_rows(model, episodes, encoder):
    law_rows=_cache_rows(model,episodes,encoder)
    raw_steps=[(episode,step) for episode in episodes for step in episode.steps]
    if len(law_rows)!=len(raw_steps): raise RuntimeError('cached policy rows do not align with raw teacher steps')
    rows=[]; model.eval()
    with torch.no_grad():
        for law_row,(episode,step) in zip(law_rows,raw_steps):
            ids,values=encode_structured_observation(step.text,max_atoms=96); ids=ids.unsqueeze(0); values=values.unsqueeze(0)
            atoms,mask=model.structured_observation_encoder.encode_atoms(ids,values)
            law=CausalLawState(slots=law_row.law_slots.unsqueeze(0),confidence=law_row.law_confidence.unsqueeze(0),usage=law_row.law_usage.unsqueeze(0))
            state=law_row.state_sketch.unsqueeze(0); actions=law_row.enriched_actions.unsqueeze(0)
            law_scores=model.causal_law_scores(state,actions,law)
            goal=model.goal_difference_scores(atoms,mask,law_scores['predicted_delta'],actions,law_scores['confidence'])
            rows.append(GoalAdvantageRow(episode.family,law_row.base_logits.clone(),goal['policy_features'][0].cpu(),law_scores['confidence'][0].cpu(),int(law_row.label)))
    return rows

def groups(rows):
    out=defaultdict(list)
    for row in rows: out[int(row.base_logits.shape[0])].append(row)
    return out

def objective(model,grouped):
    losses=[]; correct=0; total=0; family=defaultdict(lambda:[0,0])
    for _,items in grouped.items():
        base=torch.stack([r.base_logits for r in items]); features=torch.stack([r.policy_features for r in items]); conf=torch.stack([r.confidence for r in items]); labels=torch.tensor([r.label for r in items],dtype=torch.long)
        bonus=model.goal_difference_advantage_head(features).squeeze(-1)*conf.clamp(0.0,1.0); logits=base+bonus
        losses.append(F.cross_entropy(logits,labels)); pred=logits.argmax(-1); correct+=int(pred.eq(labels).sum()); total+=len(items)
        for i,row in enumerate(items): family[row.family][0]+=int(pred[i].item()==row.label); family[row.family][1]+=1
    return torch.stack(losses).mean(),{'accuracy':correct/max(1,total),'rows':total,'family':{k:c/n for k,(c,n) in family.items()}}

def causal_score(metrics):
    f=metrics['family']; return (f.get('causal_laws',0.0)+f.get('causal_switch',0.0))/2.0

def preservation_score(metrics):
    f=metrics['family']; return (f.get('goal_inference',0.0)+f.get('composition_holdout',0.0))/2.0
