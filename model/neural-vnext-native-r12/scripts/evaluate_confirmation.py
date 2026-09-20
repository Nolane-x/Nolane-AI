from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

HERE=Path(__file__).resolve()
ROOT=HERE.parents[1]
MODEL_ROOT=HERE.parents[2]
R11_ROOT=MODEL_ROOT/"neural-vnext-native-r11"
R9_ROOT=MODEL_ROOT/"neural-vnext-native-r9"
R4_ROOT=MODEL_ROOT/"neural-vnext-native-r4"
R3_ROOT=MODEL_ROOT/"neural-vnext-native-r3"
R2_ROOT=MODEL_ROOT/"neural-vnext-native-r2"
NATIVE_ROOT=MODEL_ROOT/"neural-vnext-native"
R18_ROOT=MODEL_ROOT/"r1.8"
for path in (ROOT,R11_ROOT,R9_ROOT,R4_ROOT,R3_ROOT,R2_ROOT,NATIVE_ROOT,R18_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from neural_causal_training import evaluate_r12, load_r12_checkpoint

VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")
FAMILIES=("conditional_regimes","regime_switch","implicit_goal_regimes","causal_prerequisites")


def _family_solved(result:Mapping[str,Any])->dict[str,int]:
    return {str(f):int(v["solved"]) for f,v in result["families"].items()}


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PRE_CONFIRM_LOCK.json")
    parser.add_argument("--checkpoint",required=True,type=Path)
    parser.add_argument("--parent-checkpoint",type=Path,default=R4_ROOT/"accepted"/"r4.pt")
    parser.add_argument("--result",required=True,type=Path)
    args=parser.parse_args()

    lock=json.loads(args.lock.read_text())
    if lock["status"]!="FROZEN_CONFIRMATION_UNOPENED":
        raise ValueError("R12 confirmation lock invalid")
    if lock["selected_candidate"]!="neural_causal_broad":
        raise ValueError("R12 selected candidate changed")
    if lock["confirmation"]!={"split":"dev","indices":[640,671],"episodes":128,"opened":False}:
        raise ValueError("R12 confirmation identities changed")
    if lock["fresh"]!={"split":"fresh","indices":[280,319],"episodes_expected":160,"opened":False}:
        raise ValueError("R12 fresh isolation changed")

    parent,parent_meta=load_r4_checkpoint(args.parent_checkpoint)
    if parent_meta["checkpoint_sha256"]!=lock["parent_authority"]["learned_parent_checkpoint_sha256"]:
        raise ValueError("R12 confirmation R4 checkpoint mismatch")
    if parent_meta["state_dict_sha256"]!=lock["parent_authority"]["learned_parent_state_dict_sha256"]:
        raise ValueError("R12 confirmation R4 state mismatch")
    model,metadata=load_r12_checkpoint(args.checkpoint,parent_checkpoint_path=args.parent_checkpoint)
    if metadata["checkpoint_sha256"]!=lock["frozen_candidate"]["checkpoint_sha256"]:
        raise ValueError("R12 frozen checkpoint hash changed")
    if metadata["successor_state_dict_sha256"]!=lock["frozen_candidate"]["successor_state_dict_sha256"]:
        raise ValueError("R12 frozen successor tensor digest changed")

    baseline=evaluate_r11(
        parent,
        make_task=make_r18_task,
        families=FAMILIES,
        split="dev",
        indices=(640,671),
        horizon=1,
    )
    candidate=evaluate_r12(
        model,
        make_task=make_r18_task,
        families=FAMILIES,
        split="dev",
        indices=(640,671),
    )
    pf=_family_solved(baseline); cf=_family_solved(candidate)
    family_delta={f:cf[f]-pf[f] for f in pf}
    total_delta=int(candidate["solved"])-int(baseline["solved"])
    implicit_delta=family_delta["implicit_goal_regimes"]
    visible_pass={f:family_delta[f]==0 for f in VISIBLE}
    accepted=bool(total_delta>=1 and implicit_delta>=1 and all(visible_pass.values()))
    payload={
        "schema_version":1,
        "status":"CONFIRMATION_ACCEPTED" if accepted else "CONFIRMATION_REJECTED",
        "candidate":lock["candidate"],
        "selected_candidate":lock["selected_candidate"],
        "selected_config":lock["selected_config"],
        "checkpoint_sha256":metadata["checkpoint_sha256"],
        "successor_state_dict_sha256":metadata["successor_state_dict_sha256"],
        "parent_confirmation":baseline,
        "candidate_confirmation":candidate,
        "gate":{
            "accepted":accepted,
            "parent_total_solved":int(baseline["solved"]),
            "candidate_total_solved":int(candidate["solved"]),
            "total_solved_delta_vs_parent":total_delta,
            "family_solved_delta_vs_parent":family_delta,
            "implicit_goal_delta_vs_parent":implicit_delta,
            "visible_target_family_pass":visible_pass,
            "all_visible_target_families_exact":all(visible_pass.values()),
        },
        "fresh_opened":False,
    }
    args.result.parent.mkdir(parents=True,exist_ok=True)
    args.result.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "status":payload["status"],
        "parent_solved":baseline["solved"],
        "candidate_solved":candidate["solved"],
        "parent_families":baseline["families"],
        "candidate_families":candidate["families"],
        "gate":payload["gate"],
        "fresh_opened":False,
    },sort_keys=True))
    return 0 if accepted else 2


if __name__=="__main__":
    raise SystemExit(main())
