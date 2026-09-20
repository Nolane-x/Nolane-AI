from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

HERE=Path(__file__).resolve()
ROOT=HERE.parents[1]
MODEL_ROOT=HERE.parents[2]
R4_ROOT=MODEL_ROOT/"neural-vnext-native-r4"
R3_ROOT=MODEL_ROOT/"neural-vnext-native-r3"
R2_ROOT=MODEL_ROOT/"neural-vnext-native-r2"
NATIVE_ROOT=MODEL_ROOT/"neural-vnext-native"
R18_ROOT=MODEL_ROOT/"r1.8"
for path in (ROOT,R4_ROOT,R3_ROOT,R2_ROOT,NATIVE_ROOT,R18_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import evaluate_r4, load_r4_checkpoint
from planner_runtime import evaluate_r9

VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")
FAMILIES=("conditional_regimes","regime_switch","implicit_goal_regimes","causal_prerequisites")


def _exact_identities(rows:Sequence[Mapping[str,Any]],*,split:str,start:int,end:int)->None:
    observed=[(str(row["family"]),str(row["split"]),int(row["index"])) for row in rows]
    expected={(family,split,index) for family in FAMILIES for index in range(start,end+1)}
    if len(observed)!=len(set(observed)):
        raise ValueError("duplicate fresh identities")
    if set(observed)!=expected:
        raise ValueError("fresh identities differ from locked Cartesian court")


def _family_solved(result:Mapping[str,Any])->dict[str,int]:
    return {str(f):int(row["solved"]) for f,row in result["families"].items()}


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PRE_FRESH_LOCK.json")
    parser.add_argument("--parent-checkpoint",type=Path,default=R4_ROOT/"accepted"/"r4.pt")
    parser.add_argument("--result",required=True,type=Path)
    args=parser.parse_args()

    lock=json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("status")!="FROZEN_FRESH_UNOPENED":
        raise ValueError("R9 fresh requires frozen unopened lock")
    if lock.get("candidate")!="Neural-vNext-Native-R9-PublicCounterfactualPlanner":
        raise ValueError("unexpected R9 fresh candidate")
    if lock["selected_candidate"]!="planner_narrow" or lock["selected_config"]!={"max_support":3}:
        raise ValueError("R9 frozen candidate/config changed")
    court=lock["fresh_court"]
    if court!={"benchmark":"nolane-figg18-v1","split":"fresh","families":list(FAMILIES),"index_start":200,"index_end":239,"episodes_expected":160,"opened":False}:
        raise ValueError("R9 fresh court differs from lock")

    parent,metadata=load_r4_checkpoint(args.parent_checkpoint)
    if metadata["checkpoint_sha256"]!=lock["parent"]["checkpoint_sha256"]:
        raise ValueError("R4 checkpoint mismatch")
    if metadata["state_dict_sha256"]!=lock["parent"]["state_dict_sha256"]:
        raise ValueError("R4 state mismatch")

    baseline=evaluate_r4(parent,make_task=make_r18_task,families=FAMILIES,split="fresh",indices=(200,239))
    candidate=evaluate_r9(parent,make_task=make_r18_task,families=FAMILIES,split="fresh",indices=(200,239),max_support=3)
    _exact_identities(baseline["rows"],split="fresh",start=200,end=239)
    _exact_identities(candidate["rows"],split="fresh",start=200,end=239)

    pf=_family_solved(baseline); cf=_family_solved(candidate)
    family_delta={f:cf[f]-pf[f] for f in pf}
    total_delta=int(candidate["solved"])-int(baseline["solved"])
    implicit_delta=family_delta["implicit_goal_regimes"]
    visible_pass={f:family_delta[f]==0 for f in VISIBLE}
    accepted=bool(total_delta>=1 and implicit_delta>=1 and all(visible_pass.values()))

    payload={
      "schema_version":1,
      "status":"FRESH_ACCEPTED" if accepted else "FRESH_REJECTED",
      "candidate":lock["candidate"],
      "selected_candidate":lock["selected_candidate"],
      "selected_config":lock["selected_config"],
      "parent_checkpoint_sha256":metadata["checkpoint_sha256"],
      "parent_state_dict_sha256":metadata["state_dict_sha256"],
      "parent_fresh":baseline,
      "candidate_fresh":candidate,
      "promotion_gate":{
        "accepted":accepted,
        "parent_total_solved":int(baseline["solved"]),
        "candidate_total_solved":int(candidate["solved"]),
        "total_solved_delta_vs_parent":total_delta,
        "family_solved_delta_vs_parent":family_delta,
        "target_family":"implicit_goal_regimes",
        "target_family_solved_delta_vs_parent":implicit_delta,
        "visible_target_family_pass":visible_pass,
        "all_visible_target_families_exact":all(visible_pass.values())
      },
      "post_fresh_tuning_allowed":False,
      "fresh_block_reuse_for_promotion_allowed":False
    }
    args.result.parent.mkdir(parents=True,exist_ok=True)
    args.result.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
      "status":payload["status"],
      "parent_solved":baseline["solved"],
      "candidate_solved":candidate["solved"],
      "candidate_families":candidate["families"],
      "promotion_gate":payload["promotion_gate"]
    },sort_keys=True))
    return 0 if accepted else 2


if __name__=="__main__":
    raise SystemExit(main())
