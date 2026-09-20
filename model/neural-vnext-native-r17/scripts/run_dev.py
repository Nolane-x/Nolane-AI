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
    ROOT,MODEL_ROOT/"neural-vnext-native-r11",MODEL_ROOT/"neural-vnext-native-r9",
    MODEL_ROOT/"neural-vnext-native-r4",MODEL_ROOT/"neural-vnext-native-r3",
    MODEL_ROOT/"neural-vnext-native-r2",MODEL_ROOT/"neural-vnext-native",MODEL_ROOT/"r1.8",
):
    if str(path) not in sys.path: sys.path.insert(0,str(path))

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from world_model import calibrate_threshold,collect_public_transition_dataset,ensemble_state_dict,train_ensemble
from runtime import evaluate_r17

FAMILIES=("conditional_regimes","regime_switch","implicit_goal_regimes","causal_prerequisites")
VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")


def _sha(path:Path)->str:
    h=sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--lock",type=Path,default=ROOT/"PREDEV_LOCK.json")
    ap.add_argument("--parent-checkpoint",type=Path,default=MODEL_ROOT/"neural-vnext-native-r4"/"accepted"/"r4.pt")
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    lock=json.loads(args.lock.read_text())
    assert lock["fresh_isolation"]["status"]=="UNOPENED"
    assert lock["benchmark"]["fresh_indices"]==[280,319]

    train=collect_public_transition_dataset(make_task=make_r18_task,indices=tuple(lock["training"]["train_indices"]),probe_steps=lock["training"]["probe_steps"])
    cal=collect_public_transition_dataset(make_task=make_r18_task,indices=tuple(lock["training"]["calibration_indices"]),probe_steps=lock["training"]["probe_steps"])
    models,summary=train_ensemble(
        train,seeds=lock["training"]["ensemble_seeds"],hidden_dim=lock["training"]["hidden_dim"],
        epochs=lock["training"]["epochs"],batch_size=lock["training"]["batch_size"],
        learning_rate=lock["training"]["learning_rate"],weight_decay=lock["training"]["weight_decay"],
    )
    calibration=calibrate_threshold(
        models,cal,minimum_precision=lock["calibration_gate"]["minimum_precision"],
        minimum_coverage=lock["calibration_gate"]["minimum_coverage"],
        thresholds=lock["calibration_gate"]["threshold_candidates"],
    )
    if calibration["selected"] is None:
        raise SystemExit("R17_CALIBRATION_REJECTED_FRESH_UNOPENED")
    threshold=float(calibration["selected"]["threshold"])

    parent,meta=load_r4_checkpoint(args.parent_checkpoint)
    baseline=evaluate_r11(parent,make_task=make_r18_task,families=FAMILIES,split="dev",indices=tuple(lock["benchmark"]["development_indices"]),horizon=1)
    rows=[]
    for c in lock["selection"]["candidates"]:
        ev=evaluate_r17(
            parent,make_task=make_r18_task,families=FAMILIES,split="dev",
            indices=tuple(lock["benchmark"]["development_indices"]),models=models,threshold=threshold,
            max_support=c["max_support"],horizon=c["horizon"],minimum_advantage=c["minimum_advantage"],
        )
        fd={f:int(ev["families"][f]["solved"])-int(baseline["families"][f]["solved"]) for f in FAMILIES}
        eligible=int(ev["solved"])>int(baseline["solved"]) and fd["implicit_goal_regimes"]>=1 and all(fd[f]==0 for f in VISIBLE)
        rows.append({"name":c["name"],"config":c,"evaluation":ev,"family_solved_delta_vs_parent":fd,"total_solved_delta_vs_parent":int(ev["solved"])-int(baseline["solved"]),"eligible":bool(eligible)})
    eligible=[r for r in rows if r["eligible"]]
    selected=max(eligible,key=lambda r:(r["family_solved_delta_vs_parent"]["implicit_goal_regimes"],r["total_solved_delta_vs_parent"],-r["evaluation"]["steps"],r["name"]),default=None)

    args.output.mkdir(parents=True,exist_ok=True)
    pt=args.output/"r17.pt"
    torch.save({
        "format":"nolane-neural-vnext-native-r17-model-based-planning-v1",
        "parent_checkpoint_sha256":meta["checkpoint_sha256"],"parent_state_dict_sha256":meta["state_dict_sha256"],
        "hidden_dim":lock["training"]["hidden_dim"],"ensemble_seeds":lock["training"]["ensemble_seeds"],
        "ensemble_state_dict":ensemble_state_dict(models),"calibration":calibration,"threshold":threshold,"training_summary":summary,
    },pt)
    manifest={
        "status":"R17_DEV_ELIGIBLE_FRESH_UNOPENED" if selected else "R17_DEV_REJECTED_FRESH_UNOPENED",
        "fresh_opened":False,"checkpoint_sha256":_sha(pt),
        "parent_checkpoint_sha256":meta["checkpoint_sha256"],"parent_state_dict_sha256":meta["state_dict_sha256"],
        "successor_parameters":sum(m.parameter_count() for m in models),
        "physical_parameters":877542+sum(m.parameter_count() for m in models),
        "training_examples":len(train),"calibration_examples":len(cal),
        "training_summary":summary,"calibration":calibration,"parent_development":baseline,
        "candidates":rows,"selected_candidate":None if selected is None else selected["name"],
        "selected_config":None if selected is None else selected["config"],
    }
    (args.output/"r17.dev.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "status":manifest["status"],"threshold":threshold,"calibration_selected":calibration["selected"],
        "successor_parameters":manifest["successor_parameters"],"parent_dev_solved":baseline["solved"],
        "selected_candidate":manifest["selected_candidate"],"selected_dev_solved":None if selected is None else selected["evaluation"]["solved"],
        "candidates":[{
          "name":r["name"],"solved":r["evaluation"]["solved"],
          "implicit":r["evaluation"]["families"]["implicit_goal_regimes"]["solved"],
          "overrides":r["evaluation"]["overrides_vs_r11"],"decisions":r["evaluation"]["model_based_decisions"],
          "delta":r["total_solved_delta_vs_parent"],"family_delta":r["family_solved_delta_vs_parent"],"eligible":r["eligible"]
        } for r in rows],"fresh_opened":False,
    },sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
