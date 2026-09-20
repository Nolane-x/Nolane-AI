from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

HERE=Path(__file__).resolve()
ROOT=HERE.parents[1]
MODEL_ROOT=HERE.parents[2]
R9_ROOT=MODEL_ROOT/"neural-vnext-native-r9"
R4_ROOT=MODEL_ROOT/"neural-vnext-native-r4"
R3_ROOT=MODEL_ROOT/"neural-vnext-native-r3"
R2_ROOT=MODEL_ROOT/"neural-vnext-native-r2"
NATIVE_ROOT=MODEL_ROOT/"neural-vnext-native"
R18_ROOT=MODEL_ROOT/"r1.8"
for path in (ROOT,R9_ROOT,R4_ROOT,R3_ROOT,R2_ROOT,NATIVE_ROOT,R18_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import load_r4_checkpoint
from planner_runtime import evaluate_r9
from causal_runtime import evaluate_r11

FAMILIES=("conditional_regimes","regime_switch","implicit_goal_regimes","causal_prerequisites")
VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {str(f): int(row["solved"]) for f,row in result["families"].items()}


def _exact_identities(rows: Sequence[Mapping[str,Any]]) -> None:
    observed=[(str(row["family"]),str(row["split"]),int(row["index"])) for row in rows]
    expected={(family,"fresh",index) for family in FAMILIES for index in range(240,280)}
    if len(observed)!=160 or len(set(observed))!=160:
        raise ValueError("R11 fresh court identity count/uniqueness mismatch")
    if set(observed)!=expected:
        raise ValueError("R11 fresh identities differ from locked Cartesian court")


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PRE_FRESH_LOCK.json")
    parser.add_argument("--parent-checkpoint",type=Path,default=R4_ROOT/"accepted"/"r4.pt")
    parser.add_argument("--result",required=True,type=Path)
    args=parser.parse_args()

    lock=json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("status")!="FROZEN_FRESH_UNOPENED":
        raise ValueError("R11 fresh requires frozen unopened lock")
    if lock.get("candidate")!="Neural-vNext-Native-R11-CausalVersionSpace":
        raise ValueError("unexpected R11 fresh candidate")
    if lock["selected_candidate"]!="causal_horizon1":
        raise ValueError("R11 selected candidate changed")
    if lock["selected_config"]!={"horizon":1,"max_support":3}:
        raise ValueError("R11 selected config changed")
    if lock["fresh_court"]!={
        "benchmark":"nolane-figg18-v1",
        "split":"fresh",
        "families":list(FAMILIES),
        "indices":[240,279],
        "episodes_expected":160,
        "opened":False,
    }:
        raise ValueError("R11 fresh court differs from frozen lock")

    parent,metadata=load_r4_checkpoint(args.parent_checkpoint)
    if metadata["checkpoint_sha256"]!=lock["parent_authority"]["r4_checkpoint_sha256"]:
        raise ValueError("accepted R4 checkpoint mismatch")
    if metadata["state_dict_sha256"]!=lock["parent_authority"]["r4_state_dict_sha256"]:
        raise ValueError("accepted R4 state mismatch")

    baseline=evaluate_r9(
        parent,
        make_task=make_r18_task,
        families=FAMILIES,
        split="fresh",
        indices=(240,279),
        max_support=3,
    )
    candidate=evaluate_r11(
        parent,
        make_task=make_r18_task,
        families=FAMILIES,
        split="fresh",
        indices=(240,279),
        horizon=1,
    )
    _exact_identities(baseline["rows"])
    _exact_identities(candidate["rows"])

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
        "all_visible_target_families_exact":all(visible_pass.values()),
        "step_counts_used_for_promotion":False
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
      "parent_families":baseline["families"],
      "candidate_families":candidate["families"],
      "promotion_gate":payload["promotion_gate"]
    },sort_keys=True))
    return 0 if accepted else 2


if __name__=="__main__":
    raise SystemExit(main())
