from __future__ import annotations

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


def _expected_distance(state:Tensor,posterior:Tensor)->float:
    distances=torch.remainder(GOAL_TABLE-state.unsqueeze(0),GOAL_CARDINALITY).sum(dim=1).float()
    return float((posterior*distances).sum().item())


def _future_global(base:Tensor,state:Tensor,depth:int)->Tensor:
    row=base.detach().clone()
    row[0:3]=state.float()/4.0
    row[3:6]=torch.remainder(state,2).float()
    row[14]=max(0.0,float(row[14].item())-float(depth)/32.0)
    row[15]=min(1.0,float(row[15].item())+float(depth)/32.0)
    return row


@torch.no_grad()
def _predict(
    *,
    state:Tensor,depth:int,action:int,
    global_features:Tensor,action_features:Tensor,
    models:Sequence[PublicDynamicsNet],threshold:float,
)->tuple[Tensor|None,float]:
    future=_future_global(global_features,state,depth)
    pred,agree,conf=ensemble_predictions(models,future.unsqueeze(0),action_features.unsqueeze(0))
    c=float(conf[0,int(action)].item())
    if not bool(agree[0,int(action)].item()) or c<float(threshold):
        return None,c
    delta=pred[0,int(action)].long()
    return torch.remainder(state+delta,GOAL_CARDINALITY),c


def choose_r18_action(
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
    confidence_floor:float,
    max_support:int,
    minimum_advantage:float,
)->tuple[int,dict[str,Any]]:
    r11_action,r11_info=choose_public_causal_action(
        observation=observation,exact_memory=exact_memory,causal_memory=causal_memory,
        posterior=posterior,parent_logits=parent_logits,horizon=R11_HORIZON,
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
    effective=max(float(threshold),float(confidence_floor))

    def first_transition(action:int)->tuple[Tensor|None,float]:
        certified,_=causal_memory.predict_certified(
            context=exact_memory.context_key(observation),state=state,action=int(action)
        )
        if certified is not None:
            return certified,1.0
        return _predict(
            state=state,depth=0,action=int(action),
            global_features=global_features,action_features=action_features,
            models=models,threshold=effective,
        )

    firsts:dict[int,tuple[Tensor,float,float]]={}
    for action in actions:
        nxt,conf=first_transition(action)
        if nxt is None:
            continue
        firsts[int(action)]=(nxt,float(conf),_expected_distance(nxt,posterior))

    # Parent reference is allowed one extra imagined continuation. This can
    # only make R11 harder to replace; alternatives are never selected for
    # their imagined second step.
    if int(r11_action)==submit:
        parent_reference=_expected_distance(state,posterior)
    elif int(r11_action) not in firsts:
        return int(r11_action),{"override":False,"reason":"r11_reference_not_modelable","support":support}
    else:
        rstate,rconf,rdist=firsts[int(r11_action)]
        parent_reference=float(rdist)
        for action in actions:
            nxt,conf=_predict(
                state=rstate,depth=1,action=int(action),
                global_features=global_features,action_features=action_features,
                models=models,threshold=effective,
            )
            if nxt is None:
                continue
            parent_reference=min(parent_reference,_expected_distance(nxt,posterior))

    candidates=[]
    for action,(nxt,conf,dist) in firsts.items():
        if int(action)==int(r11_action):
            continue
        if float(dist)+float(minimum_advantage)>=float(parent_reference)-1e-8:
            continue
        candidates.append((float(dist),-float(conf),-float(parent_logits[action].item()),int(action),float(conf)))
    if not candidates:
        return int(r11_action),{
            "override":False,"reason":"no_safe_first_step_advantage","support":support,
            "effective_threshold":effective,"parent_reference_distance":float(parent_reference),
        }
    candidates.sort()
    dist,_nconf,_nlogit,action,conf=candidates[0]
    return int(action),{
        "override":True,"reason":"safe_first_step_neural_advantage","support":support,
        "effective_threshold":effective,"parent_reference_distance":float(parent_reference),
        "selected_distance":float(dist),"selected_confidence":float(conf),
    }


def rollout_r18(
    parent:NativeR4LatentGoalBeliefPolicy,task:Any,*,
    models:Sequence[PublicDynamicsNet],threshold:float,confidence_floor:float,
    max_support:int,minimum_advantage:float,
)->dict[str,Any]:
    exact_memory=PublicActionMemory(len(task.action_descriptions))
    causal_memory=PublicCausalRuleMemory()
    trace=PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed=PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief=PublicGoalConsistencyBelief()
    hidden=parent.init_parent_hidden(1)
    previous_feedback=[0.0,0.0,0.0]
    overrides=decisions=0
    while not task.done:
        observation=task.observe()
        belief.update(observation)
        g,a,v=encode_public_state(observation,exact_memory,previous_feedback=previous_feedback)
        tf,tv=trace.encode(); af,av=attributed.encode()
        with torch.no_grad():
            out=parent.forward_step(
                g.unsqueeze(0),a.unsqueeze(0),v.unsqueeze(0),hidden,
                tf.unsqueeze(0),tv.unsqueeze(0),af.unsqueeze(0),av.unsqueeze(0),
            )
        hidden=out["next_parent_hidden"]
        action,info=choose_r18_action(
            observation=observation,exact_memory=exact_memory,causal_memory=causal_memory,
            posterior=belief.encode(),parent_logits=out["action_logits"][0],
            global_features=g,action_features=a,models=models,threshold=threshold,
            confidence_floor=confidence_floor,max_support=max_support,minimum_advantage=minimum_advantage,
        )
        overrides+=int(bool(info.get("override",False)))
        decisions+=int(info.get("reason")=="safe_first_step_neural_advantage")
        selected=a[action].detach().clone()
        before=observation
        result=task.step(int(action)); after=result.observation
        exact_memory.update(action=int(action),before=before,after=after,progress_delta=result.progress_delta,information_gain=result.information_gain,failed=result.failed)
        causal_memory.update(action=int(action),before=before,after=after)
        trace.update(before=before,after=after,progress_delta=result.progress_delta,information_gain=result.information_gain,failed=result.failed)
        attributed.update(selected_action_features=selected,before=before,after=after,progress_delta=result.progress_delta,information_gain=result.information_gain,failed=result.failed)
        previous_feedback=[float(result.progress_delta),float(result.information_gain),float(result.failed)]
    return {"solved":bool(task.solved),"steps":int(task.step_count),"overrides_vs_r11":overrides,"safe_first_step_decisions":decisions}


def evaluate_r18(
    parent:NativeR4LatentGoalBeliefPolicy,*,make_task:Any,families:Sequence[str],split:str,indices:tuple[int,int],
    models:Sequence[PublicDynamicsNet],threshold:float,confidence_floor:float,max_support:int,minimum_advantage:float,
)->dict[str,Any]:
    if split not in {"dev","fresh"}: raise ValueError("R18 split must be dev or fresh")
    rows=[]; fr={}; solved=steps=overrides=decisions=0
    for family in families:
        fs=fst=fov=fdec=episodes=0
        for index in range(int(indices[0]),int(indices[1])+1):
            row=rollout_r18(
                parent,make_task(str(family),str(split),int(index)),models=models,threshold=threshold,
                confidence_floor=confidence_floor,max_support=max_support,minimum_advantage=minimum_advantage,
            )
            fs+=int(row["solved"]); fst+=int(row["steps"]); fov+=int(row["overrides_vs_r11"]); fdec+=int(row["safe_first_step_decisions"])
            solved+=int(row["solved"]); steps+=int(row["steps"]); overrides+=int(row["overrides_vs_r11"]); decisions+=int(row["safe_first_step_decisions"])
            episodes+=1; rows.append({"family":str(family),"split":str(split),"index":int(index),**row})
        fr[str(family)]={"episodes":episodes,"solved":fs,"steps":fst,"overrides_vs_r11":fov,"safe_first_step_decisions":fdec}
    return {"split":split,"indices":[indices[0],indices[1]],"episodes":len(rows),"solved":solved,"steps":steps,"overrides_vs_r11":overrides,"safe_first_step_decisions":decisions,"families":fr,"rows":rows}
