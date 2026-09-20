from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import GOAL_CARDINALITY, GOAL_TABLE, PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from world_model import PublicDynamicsNet, ensemble_predictions

R11_HORIZON=1


@dataclass(frozen=True)
class Plan:
    first_action:int
    final_distance:float
    sequence:tuple[int,...]
    min_confidence:float


def _expected_distance(state:Tensor,posterior:Tensor)->float:
    distances=torch.remainder(GOAL_TABLE-state.unsqueeze(0),GOAL_CARDINALITY).sum(dim=1).float()
    return float((posterior*distances).sum().item())


def _future_global(base:Tensor,state:Tensor,depth:int)->Tensor:
    row=base.detach().clone()
    row[0:3]=state.float()/4.0
    row[3:6]=torch.remainder(state,2).float()
    # Hidden-target target/distance slots remain zero. Progress feedback is
    # intentionally held fixed because it is goal-dependent and unavailable
    # under counterfactual public simulation.
    row[14]=max(0.0,float(row[14].item())-float(depth)/32.0)
    row[15]=min(1.0,float(row[15].item())+float(depth)/32.0)
    return row


@torch.no_grad()
def _neural_transition(
    *,
    state:Tensor,
    depth:int,
    action:int,
    global_features:Tensor,
    action_features:Tensor,
    models:Sequence[PublicDynamicsNet],
    threshold:float,
)->tuple[Tensor|None,float]:
    future=_future_global(global_features,state,depth)
    pred,agreement,confidence=ensemble_predictions(
        models,future.unsqueeze(0),action_features.unsqueeze(0)
    )
    if not bool(agreement[0,int(action)].item()):
        return None,float(confidence[0,int(action)].item())
    conf=float(confidence[0,int(action)].item())
    if conf<float(threshold):
        return None,conf
    delta=pred[0,int(action)].long()
    return torch.remainder(state+delta,GOAL_CARDINALITY),conf


def choose_r17_action(
    *,
    observation:Mapping[str,Any],
    exact_memory:PublicActionMemory,
    causal_memory:PublicCausalRuleMemory,
    posterior:Tensor,
    parent_logits:Tensor,
    global_features:Tensor,
    action_features:Tensor,
    models:Sequence[PublicDynamicsNet],
    threshold:float,
    max_support:int,
    horizon:int,
    minimum_advantage:float,
)->tuple[int,dict[str,Any]]:
    r11_action,r11_info=choose_public_causal_action(
        observation=observation,
        exact_memory=exact_memory,
        causal_memory=causal_memory,
        posterior=posterior,
        parent_logits=parent_logits,
        horizon=R11_HORIZON,
    )
    target=observation.get("target")
    if isinstance(target,list) and len(target)==3:
        return int(r11_action),{"override":False,"reason":"visible_target_r11_exact"}
    if r11_info.get("reason")=="r9_public_progress_complete":
        return int(r11_action),{"override":False,"reason":"public_progress_complete"}

    posterior=posterior.detach().float()
    posterior=posterior/posterior.sum().clamp_min(1e-12)
    support=int((posterior>0).sum().item())
    if support>int(max_support):
        return int(r11_action),{"override":False,"reason":"posterior_support_gate","support":support}

    descriptions=observation["actions"]
    submits=[i for i,d in enumerate(descriptions) if "submit" in str(d).lower()]
    if len(submits)!=1:
        raise ValueError("expected exactly one submit action")
    submit=int(submits[0])
    actions=[i for i in range(len(descriptions)) if i!=submit]
    state=torch.tensor(observation["state"],dtype=torch.long)

    def first_transition(action:int)->tuple[Tensor|None,float]:
        certified,_count=causal_memory.predict_certified(
            context=exact_memory.context_key(observation),
            state=state,
            action=int(action),
        )
        if certified is not None:
            return certified,1.0
        return _neural_transition(
            state=state,depth=0,action=int(action),
            global_features=global_features,action_features=action_features,
            models=models,threshold=float(threshold),
        )

    plans:dict[int,Plan]={}
    def consider(first:int,current:Tensor,sequence:tuple[int,...],depth:int,min_conf:float)->None:
        plan=Plan(
            first_action=int(first),
            final_distance=_expected_distance(current,posterior),
            sequence=sequence,
            min_confidence=float(min_conf),
        )
        old=plans.get(int(first))
        rank=(-plan.final_distance,plan.min_confidence,-len(plan.sequence),tuple(-x for x in plan.sequence))
        old_rank=None if old is None else (-old.final_distance,old.min_confidence,-len(old.sequence),tuple(-x for x in old.sequence))
        if old is None or rank>old_rank:
            plans[int(first)]=plan
        if depth>=int(horizon):
            return
        for action in actions:
            nxt,conf=_neural_transition(
                state=current,depth=depth,action=int(action),
                global_features=global_features,action_features=action_features,
                models=models,threshold=float(threshold),
            )
            if nxt is None:
                continue
            signature=tuple(int(v) for v in nxt.tolist())
            visited={tuple(int(v) for v in state.tolist())}
            visited.update(
                tuple(int(v) for v in state.tolist())
                for _ in ()
            )
            if signature==tuple(int(v) for v in current.tolist()):
                continue
            consider(
                first,nxt,sequence+(int(action),),depth+1,min(float(min_conf),float(conf))
            )

    eligible_first=0
    for action in actions:
        nxt,conf=first_transition(int(action))
        if nxt is None:
            continue
        eligible_first+=1
        consider(int(action),nxt,(int(action),),1,float(conf))

    r11_plan=plans.get(int(r11_action))
    if int(r11_action)==submit:
        reference=_expected_distance(state,posterior)
    elif r11_plan is not None:
        reference=float(r11_plan.final_distance)
    else:
        return int(r11_action),{
            "override":False,
            "reason":"r11_reference_not_modelable",
            "support":support,
            "eligible_first_actions":eligible_first,
        }

    alternatives=[p for a,p in plans.items() if int(a)!=int(r11_action)]
    if not alternatives:
        return int(r11_action),{
            "override":False,"reason":"no_model_based_alternative",
            "support":support,"eligible_first_actions":eligible_first,
        }
    best=max(
        alternatives,
        key=lambda p:(-p.final_distance,p.min_confidence,float(parent_logits[p.first_action].item()),-p.first_action),
    )
    if float(best.final_distance)+float(minimum_advantage)>=float(reference)-1e-8:
        return int(r11_action),{
            "override":False,"reason":"no_model_based_advantage",
            "support":support,"eligible_first_actions":eligible_first,
            "reference_distance":float(reference),
            "best_alternative_distance":float(best.final_distance),
        }
    return int(best.first_action),{
        "override":True,
        "reason":"model_based_neural_advantage",
        "support":support,
        "eligible_first_actions":eligible_first,
        "reference_distance":float(reference),
        "selected_distance":float(best.final_distance),
        "selected_sequence":[int(v) for v in best.sequence],
        "selected_min_confidence":float(best.min_confidence),
    }


def rollout_r17(
    parent:NativeR4LatentGoalBeliefPolicy,
    task:Any,
    *,
    models:Sequence[PublicDynamicsNet],
    threshold:float,
    max_support:int,
    horizon:int,
    minimum_advantage:float,
)->dict[str,Any]:
    exact_memory=PublicActionMemory(len(task.action_descriptions))
    causal_memory=PublicCausalRuleMemory()
    trace=PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed=PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief=PublicGoalConsistencyBelief()
    hidden=parent.init_parent_hidden(1)
    previous_feedback=[0.0,0.0,0.0]
    overrides=decisions=0
    max_planned_depth=0

    while not task.done:
        observation=task.observe()
        belief.update(observation)
        global_features,action_features,valid=encode_public_state(
            observation,exact_memory,previous_feedback=previous_feedback
        )
        trace_features,trace_valid=trace.encode()
        attribution_features,attribution_valid=attributed.encode()
        with torch.no_grad():
            output=parent.forward_step(
                global_features.unsqueeze(0),action_features.unsqueeze(0),valid.unsqueeze(0),
                hidden,trace_features.unsqueeze(0),trace_valid.unsqueeze(0),
                attribution_features.unsqueeze(0),attribution_valid.unsqueeze(0),
            )
        hidden=output["next_parent_hidden"]
        action,info=choose_r17_action(
            observation=observation,exact_memory=exact_memory,causal_memory=causal_memory,
            posterior=belief.encode(),parent_logits=output["action_logits"][0],
            global_features=global_features,action_features=action_features,
            models=models,threshold=float(threshold),max_support=int(max_support),
            horizon=int(horizon),minimum_advantage=float(minimum_advantage),
        )
        overrides+=int(bool(info.get("override",False)))
        decisions+=int(info.get("reason")=="model_based_neural_advantage")
        seq=info.get("selected_sequence") or []
        max_planned_depth=max(max_planned_depth,len(seq))

        selected_action_features=action_features[action].detach().clone()
        before=observation
        result=task.step(int(action))
        after=result.observation
        exact_memory.update(
            action=int(action),before=before,after=after,
            progress_delta=result.progress_delta,information_gain=result.information_gain,failed=result.failed,
        )
        causal_memory.update(action=int(action),before=before,after=after)
        trace.update(before=before,after=after,progress_delta=result.progress_delta,information_gain=result.information_gain,failed=result.failed)
        attributed.update(
            selected_action_features=selected_action_features,before=before,after=after,
            progress_delta=result.progress_delta,information_gain=result.information_gain,failed=result.failed,
        )
        previous_feedback=[float(result.progress_delta),float(result.information_gain),float(result.failed)]

    return {
        "solved":bool(task.solved),
        "steps":int(task.step_count),
        "overrides_vs_r11":int(overrides),
        "model_based_decisions":int(decisions),
        "max_planned_depth":int(max_planned_depth),
    }


def evaluate_r17(
    parent:NativeR4LatentGoalBeliefPolicy,
    *,
    make_task:Any,
    families:Sequence[str],
    split:str,
    indices:tuple[int,int],
    models:Sequence[PublicDynamicsNet],
    threshold:float,
    max_support:int,
    horizon:int,
    minimum_advantage:float,
)->dict[str,Any]:
    if split not in {"dev","fresh"}:
        raise ValueError("R17 evaluation split must be dev or fresh")
    rows=[]
    fr={}
    solved=steps=overrides=decisions=0
    for family in families:
        fs=fst=fov=fdec=episodes=0
        for index in range(int(indices[0]),int(indices[1])+1):
            row=rollout_r17(
                parent,make_task(str(family),str(split),int(index)),
                models=models,threshold=float(threshold),max_support=int(max_support),
                horizon=int(horizon),minimum_advantage=float(minimum_advantage),
            )
            fs+=int(row["solved"]); fst+=int(row["steps"]); fov+=int(row["overrides_vs_r11"]); fdec+=int(row["model_based_decisions"])
            solved+=int(row["solved"]); steps+=int(row["steps"]); overrides+=int(row["overrides_vs_r11"]); decisions+=int(row["model_based_decisions"])
            episodes+=1
            rows.append({"family":str(family),"split":str(split),"index":int(index),**row})
        fr[str(family)]={"episodes":episodes,"solved":fs,"steps":fst,"overrides_vs_r11":fov,"model_based_decisions":fdec}
    return {
        "split":str(split),"indices":[int(indices[0]),int(indices[1])],"episodes":len(rows),
        "solved":solved,"steps":steps,"overrides_vs_r11":overrides,"model_based_decisions":decisions,
        "families":fr,"rows":rows,
    }
