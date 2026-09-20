from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import torch

HERE=Path(__file__).resolve()
ROOT=HERE.parents[1]
MODEL_ROOT=HERE.parents[2]
for path in (
    ROOT,
    MODEL_ROOT/"neural-vnext-native-r11",
    MODEL_ROOT/"neural-vnext-native-r9",
    MODEL_ROOT/"neural-vnext-native-r4",
    MODEL_ROOT/"neural-vnext-native-r3",
    MODEL_ROOT/"neural-vnext-native-r2",
    MODEL_ROOT/"neural-vnext-native",
    MODEL_ROOT/"r1.8",
):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from world_model import (
    calibrate_threshold,
    collect_public_transition_dataset,
    ensemble_state_dict,
    train_ensemble,
)
from runtime import evaluate_r16

FAMILIES=("conditional_regimes","regime_switch","implicit_goal_regimes","causal_prerequisites")
VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")


def _sha256_file(path:Path)->str:
    h=sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint",type=Path,default=MODEL_ROOT/"neural-vnext-native-r4"/"accepted"/"r4.pt")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    lock=json.loads(args.lock.read_text(encoding="utf-8"))
    assert lock["status"]=="PREDEVELOPMENT_LOCKED"
    assert lock["fresh_isolation"]["status"]=="UNOPENED"
    assert lock["benchmark"]["fresh_indices"]==[280,319]

    train=collect_public_transition_dataset(
        make_task=make_r18_task,
        indices=tuple(lock["training"]["train_indices"]),
        probe_steps=int(lock["training"]["probe_steps"]),
    )
    calibration=collect_public_transition_dataset(
        make_task=make_r18_task,
        indices=tuple(lock["training"]["calibration_indices"]),
        probe_steps=int(lock["training"]["probe_steps"]),
    )
    models,training_summary=train_ensemble(
        train,
        seeds=lock["training"]["ensemble_seeds"],
        hidden_dim=int(lock["training"]["hidden_dim"]),
        epochs=int(lock["training"]["epochs"]),
        batch_size=int(lock["training"]["batch_size"]),
        learning_rate=float(lock["training"]["learning_rate"]),
        weight_decay=float(lock["training"]["weight_decay"]),
    )
    calibration_result=calibrate_threshold(
        models,
        calibration,
        minimum_precision=float(lock["calibration_gate"]["minimum_precision"]),
        minimum_coverage=int(lock["calibration_gate"]["minimum_coverage"]),
        thresholds=lock["calibration_gate"]["threshold_candidates"],
    )
    if calibration_result["selected"] is None:
        raise SystemExit("R16_CALIBRATION_REJECTED_FRESH_UNOPENED")
    threshold=float(calibration_result["selected"]["threshold"])

    parent,metadata=load_r4_checkpoint(args.parent_checkpoint)
    baseline=evaluate_r11(
        parent,
        make_task=make_r18_task,
        families=FAMILIES,
        split="dev",
        indices=tuple(lock["benchmark"]["development_indices"]),
        horizon=1,
    )
    candidates=[]
    for candidate in lock["selection"]["candidates"]:
        result=evaluate_r16(
            parent,
            make_task=make_r18_task,
            families=FAMILIES,
            split="dev",
            indices=tuple(lock["benchmark"]["development_indices"]),
            models=models,
            threshold=threshold,
            max_support=int(candidate["max_support"]),
            minimum_advantage=float(candidate["minimum_advantage"]),
        )
        family_delta={
            f:int(result["families"][f]["solved"])-int(baseline["families"][f]["solved"])
            for f in FAMILIES
        }
        eligible=(
            int(result["solved"])>int(baseline["solved"])
            and family_delta["implicit_goal_regimes"]>=1
            and all(family_delta[f]==0 for f in VISIBLE)
        )
        candidates.append({
            "name":candidate["name"],
            "config":candidate,
            "evaluation":result,
            "family_solved_delta_vs_parent":family_delta,
            "total_solved_delta_vs_parent":int(result["solved"])-int(baseline["solved"]),
            "eligible":bool(eligible),
        })
    eligible=[row for row in candidates if row["eligible"]]
    selected=max(
        eligible,
        key=lambda row:(
            row["family_solved_delta_vs_parent"]["implicit_goal_regimes"],
            row["total_solved_delta_vs_parent"],
            -int(row["evaluation"]["steps"]),
            row["name"],
        ),
        default=None,
    )

    args.output.mkdir(parents=True,exist_ok=True)
    checkpoint=args.output/"r16.pt"
    torch.save({
        "format":"nolane-neural-vnext-native-r16-public-dynamics-ensemble-v1",
        "parent_checkpoint_sha256":metadata["checkpoint_sha256"],
        "parent_state_dict_sha256":metadata["state_dict_sha256"],
        "hidden_dim":int(lock["training"]["hidden_dim"]),
        "ensemble_seeds":list(lock["training"]["ensemble_seeds"]),
        "ensemble_state_dict":ensemble_state_dict(models),
        "calibration":calibration_result,
        "threshold":threshold,
        "training_summary":training_summary,
    },checkpoint)
    manifest={
        "status":"R16_DEV_ELIGIBLE_FRESH_UNOPENED" if selected else "R16_DEV_REJECTED_FRESH_UNOPENED",
        "fresh_opened":False,
        "checkpoint_sha256":_sha256_file(checkpoint),
        "parent_checkpoint_sha256":metadata["checkpoint_sha256"],
        "parent_state_dict_sha256":metadata["state_dict_sha256"],
        "ensemble_members":len(models),
        "successor_parameters":sum(m.parameter_count() for m in models),
        "physical_parameters":877542+sum(m.parameter_count() for m in models),
        "training_examples":len(train),
        "calibration_examples":len(calibration),
        "training_summary":training_summary,
        "calibration":calibration_result,
        "parent_development":baseline,
        "candidates":candidates,
        "selected_candidate":None if selected is None else selected["name"],
        "selected_config":None if selected is None else selected["config"],
    }
    (args.output/"r16.dev.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":manifest["status"],
        "threshold":threshold,
        "calibration_selected":calibration_result["selected"],
        "successor_parameters":manifest["successor_parameters"],
        "parent_dev_solved":baseline["solved"],
        "selected_candidate":manifest["selected_candidate"],
        "selected_dev_solved":None if selected is None else selected["evaluation"]["solved"],
        "candidates":[{
            "name":row["name"],
            "solved":row["evaluation"]["solved"],
            "implicit":row["evaluation"]["families"]["implicit_goal_regimes"]["solved"],
            "overrides":row["evaluation"]["overrides_vs_r11"],
            "decisions":row["evaluation"]["neural_dynamics_decisions"],
            "delta":row["total_solved_delta_vs_parent"],
            "family_delta":row["family_solved_delta_vs_parent"],
            "eligible":row["eligible"],
        } for row in candidates],
        "fresh_opened":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
