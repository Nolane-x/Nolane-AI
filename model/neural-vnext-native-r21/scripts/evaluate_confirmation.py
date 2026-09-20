from __future__ import annotations

import argparse
import json
from hashlib import sha256
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
from goal_belief_training import evaluate_r21, load_checkpoint

VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _family_solved(result: Mapping[str,Any]) -> dict[str,int]:
    return {str(f):int(v["solved"]) for f,v in result["families"].items()}


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PRE_CONFIRM_LOCK.json")
    parser.add_argument("--parent-checkpoint",type=Path,default=R4_ROOT/"accepted"/"r4.pt")
    parser.add_argument("--checkpoint",required=True,type=Path)
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--primary-result",required=True,type=Path)
    parser.add_argument("--result",required=True,type=Path)
    args=parser.parse_args()

    lock=json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("status")!="FROZEN_CONFIRMATION_UNOPENED":
        raise ValueError("R21 confirmation requires frozen unopened lock")
    if lock["selected_candidate"]!="goalblend100":
        raise ValueError("R21 selected candidate changed")
    if lock["selected_config"]!={"beta":1.0,"max_support":3,"temperature":2.0}:
        raise ValueError("R21 selected config changed")
    if lock["confirmation"]["indices"]!=[1216,1247] or lock["confirmation"]["opened"] is not False:
        raise ValueError("R21 confirmation identity changed")
    if lock["fresh"]!={"split":"fresh","indices":[280,319],"opened":False}:
        raise ValueError("R21 fresh isolation changed")

    frozen=lock["frozen_checkpoint"]
    if _sha256_file(args.checkpoint)!=frozen["checkpoint_sha256"]:
        raise ValueError("R21 checkpoint bytes changed")
    if _sha256_file(args.manifest)!=frozen["manifest_sha256"]:
        raise ValueError("R21 manifest bytes changed")
    if _sha256_file(args.primary_result)!=frozen["dev_result_sha256"]:
        raise ValueError("R21 primary result bytes changed")

    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest["selected_candidate"]!="goalblend100":
        raise ValueError("artifact selected candidate mismatch")
    if manifest["selected_config"]!={"beta":1.0,"max_support":3,"temperature":2.0}:
        raise ValueError("artifact selected config mismatch")
    if manifest["checkpoint_sha256"]!=frozen["checkpoint_sha256"]:
        raise ValueError("artifact checkpoint digest mismatch")
    if manifest["state_dict_sha256"]!=frozen["state_dict_sha256"]:
        raise ValueError("artifact state digest mismatch")
    if int(manifest["successor_parameters"])!=107799 or int(manifest["physical_parameters"])!=985341:
        raise ValueError("artifact parameter authority changed")
    if manifest["fresh_opened"] is not False:
        raise ValueError("primary artifact unexpectedly opened fresh")

    parent,parent_metadata=load_r4_checkpoint(args.parent_checkpoint)
    if parent_metadata["checkpoint_sha256"]!=lock["learned_parent"]["checkpoint_sha256"]:
        raise ValueError("accepted R4 checkpoint mismatch")
    if parent_metadata["state_dict_sha256"]!=lock["learned_parent"]["state_dict_sha256"]:
        raise ValueError("accepted R4 state mismatch")
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    model,metadata=load_checkpoint(args.checkpoint)
    if metadata["checkpoint_sha256"]!=frozen["checkpoint_sha256"]:
        raise ValueError("loaded R21 checkpoint mismatch")
    if metadata["state_dict_sha256"]!=frozen["state_dict_sha256"]:
        raise ValueError("loaded R21 state mismatch")

    families=tuple(lock["confirmation"]["families"])
    indices=tuple(lock["confirmation"]["indices"])
    baseline=evaluate_r11(parent,make_task=make_r18_task,families=families,split="dev",indices=indices,horizon=1)
    candidate=evaluate_r21(
        parent,model,make_task=make_r18_task,families=families,split="dev",indices=indices,
        beta=1.0,temperature=2.0,max_support=3,
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
      "selected_candidate":"goalblend100",
      "selected_config":{"beta":1.0,"max_support":3,"temperature":2.0},
      "checkpoint_sha256":metadata["checkpoint_sha256"],
      "state_dict_sha256":metadata["state_dict_sha256"],
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
    args.result.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
      "status":payload["status"],
      "parent_solved":baseline["solved"],
      "candidate_solved":candidate["solved"],
      "parent_families":baseline["families"],
      "candidate_families":candidate["families"],
      "gate":payload["gate"],
      "checkpoint_sha256":metadata["checkpoint_sha256"],
      "fresh_opened":False,
    },sort_keys=True))
    return 0 if accepted else 2


if __name__=="__main__":
    raise SystemExit(main())
