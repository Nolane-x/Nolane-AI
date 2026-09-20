from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

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


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {str(f): int(row["solved"]) for f, row in result["families"].items()}


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k != "rows"}


def _eligibility(parent: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    pf=_family_solved(parent); cf=_family_solved(candidate)
    visible=("conditional_regimes","regime_switch","causal_prerequisites")
    visible_exact=all(cf[f]==pf[f] for f in visible)
    implicit=cf["implicit_goal_regimes"]-pf["implicit_goal_regimes"]
    total=int(candidate["solved"])-int(parent["solved"])
    return {
        "eligible": bool(visible_exact and implicit > 0 and total > 0),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_parent": implicit,
        "total_solved_delta_vs_parent": total,
        "family_solved_delta_vs_parent": {f: cf[f]-pf[f] for f in pf},
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint",type=Path,default=R4_ROOT/"accepted"/"r4.pt")
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--dev-result",required=True,type=Path)
    args=parser.parse_args()

    lock=json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("candidate")!="Neural-vNext-Native-R11-CausalVersionSpace":
        raise ValueError("unexpected R11 candidate identity")
    if lock["fresh_isolation"]["status"]!="UNOPENED":
        raise ValueError("R11 fresh must remain unopened")
    if lock["benchmark"]["development_indices"]!=[544,575]:
        raise ValueError("R11 primary dev identities changed")
    if lock["benchmark"]["confirmation_indices"]!=[576,607]:
        raise ValueError("R11 confirmation identities changed")
    if lock["benchmark"]["fresh_indices"]!=[240,279]:
        raise ValueError("R11 fresh identities changed")

    parent,metadata=load_r4_checkpoint(args.parent_checkpoint)
    if metadata["checkpoint_sha256"]!=lock["r9_parent"]["r4_checkpoint_sha256"]:
        raise ValueError("accepted R4 checkpoint mismatch")
    if metadata["state_dict_sha256"]!=lock["r9_parent"]["r4_state_dict_sha256"]:
        raise ValueError("accepted R4 state mismatch")

    families=tuple(lock["benchmark"]["families"])
    indices=tuple(lock["benchmark"]["development_indices"])
    baseline=evaluate_r9(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=indices,
        max_support=3,
    )
    print(json.dumps({
        "status":"R11_ACCEPTED_R9_BASELINE_FRESH_UNOPENED",
        "parent_dev_solved":baseline["solved"],
        "parent_dev_families":baseline["families"],
        "dev_indices":list(indices),
    },sort_keys=True))

    rows=[]; selected=None
    for cfg in lock["selection"]["candidates"]:
        result=evaluate_r11(
            parent,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=indices,
            horizon=int(cfg["horizon"]),
        )
        eligibility=_eligibility(baseline,result)
        rank=(
            int(result["families"]["implicit_goal_regimes"]["solved"]),
            int(result["solved"]),
            -int(result["steps"]),
            str(cfg["name"]),
        )
        row={
            "name":cfg["name"],
            "config":{"horizon":int(cfg["horizon"]),"max_support":3},
            "development":_compact(result),
            "eligibility":eligibility,
            "rank":list(rank),
        }
        rows.append(row)
        print(json.dumps({
            "candidate":cfg["name"],
            "dev_solved":result["solved"],
            "dev_families":result["families"],
            "eligibility":eligibility,
            "rank":list(rank),
            "fresh_opened":False,
        },sort_keys=True))
        if eligibility["eligible"] and (selected is None or rank>selected["rank"]):
            selected={"row":row,"rank":rank,"result":result}

    payload={
        "schema_version":1,
        "status":"R11_DEV_ELIGIBLE_FRESH_UNOPENED" if selected else "R11_DEV_NO_ELIGIBLE_CANDIDATE_FRESH_UNOPENED",
        "candidate":"Neural-vNext-Native-R11-CausalVersionSpace",
        "parent_authority":"Neural-vNext-Native-R9-PublicCounterfactualPlanner",
        "parent_checkpoint_sha256":metadata["checkpoint_sha256"],
        "parent_state_dict_sha256":metadata["state_dict_sha256"],
        "parent_development":_compact(baseline),
        "candidates":rows,
        "selected_candidate":selected["row"]["name"] if selected else None,
        "selected_config":selected["row"]["config"] if selected else None,
        "selected_rank":list(selected["rank"]) if selected else None,
        "selected_eligibility":selected["row"]["eligibility"] if selected else None,
        "successor_parameters":0,
        "physical_parameters":877542,
        "fresh_opened":False,
    }
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    args.dev_result.write_text(json.dumps({
        "parent":baseline,
        "selected":selected["result"] if selected else None,
        "candidates":rows,
        "fresh_opened":False,
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":payload["status"],
        "selected_candidate":payload["selected_candidate"],
        "selected_config":payload["selected_config"],
        "parent_dev_solved":baseline["solved"],
        "selected_dev_solved":selected["result"]["solved"] if selected else None,
        "fresh_opened":False,
    },sort_keys=True))
    return 0 if selected else 2


if __name__=="__main__":
    raise SystemExit(main())
