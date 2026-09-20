from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import torch

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

from cogcoder.r18_benchmark import make_r18_task, oracle_plan
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from neural_causal_core import NativeR12NeuralCausalResidualPolicy
from neural_causal_training import (
    evaluate_r12,
    load_lock,
    save_r12_checkpoint,
    train_r12_policy,
)


def _sha256_file(path:Path)->str:
    return sha256(path.read_bytes()).hexdigest()


def _configure(seed:int)->dict[str,Any]:
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    torch.use_deterministic_algorithms(True)
    torch.backends.mkldnn.enabled=False
    torch.set_float32_matmul_precision("highest")
    torch.set_flush_denormal(True)
    torch.manual_seed(int(seed))
    return {
        "seed":int(seed),
        "deterministic_algorithms":bool(torch.are_deterministic_algorithms_enabled()),
        "mkldnn_enabled":bool(torch.backends.mkldnn.enabled),
        "num_threads":int(torch.get_num_threads()),
    }


def _compact(result:Mapping[str,Any])->dict[str,Any]:
    return {k:v for k,v in result.items() if k!="rows"}


def _family_solved(result:Mapping[str,Any])->dict[str,int]:
    return {str(f):int(v["solved"]) for f,v in result["families"].items()}


def _eligibility(parent:Mapping[str,Any],candidate:Mapping[str,Any])->dict[str,Any]:
    pf=_family_solved(parent); cf=_family_solved(candidate)
    visible=("conditional_regimes","regime_switch","causal_prerequisites")
    visible_exact=all(cf[f]==pf[f] for f in visible)
    implicit=cf["implicit_goal_regimes"]-pf["implicit_goal_regimes"]
    total=int(candidate["solved"])-int(parent["solved"])
    return {
        "eligible":bool(visible_exact and implicit>0 and total>0),
        "visible_target_families_exact":visible_exact,
        "implicit_goal_delta_vs_parent":implicit,
        "total_solved_delta_vs_parent":total,
        "family_solved_delta_vs_parent":{f:cf[f]-pf[f] for f in pf},
    }


def _rank(result:Mapping[str,Any],name:str)->tuple[int,int,int,str]:
    return (
        int(result["families"]["implicit_goal_regimes"]["solved"]),
        int(result["solved"]),
        -int(result["steps"]),
        str(name),
    )


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",type=Path,default=ROOT/"PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint",type=Path,default=R4_ROOT/"accepted"/"r4.pt")
    parser.add_argument("--checkpoint",required=True,type=Path)
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--dev-result",required=True,type=Path)
    args=parser.parse_args()

    lock=load_lock(args.lock)
    benchmark=lock["benchmark"]
    training=lock["training"]
    seed=int(training["seed"])
    runtime=_configure(seed)

    parent,parent_metadata=load_r4_checkpoint(args.parent_checkpoint)
    if parent_metadata["checkpoint_sha256"]!=lock["learned_parent"]["checkpoint_sha256"]:
        raise ValueError("accepted R4 checkpoint mismatch")
    if parent_metadata["state_dict_sha256"]!=lock["learned_parent"]["state_dict_sha256"]:
        raise ValueError("accepted R4 state mismatch")
    for p in parent.parameters():
        p.requires_grad_(False)
    parent.eval()

    families=tuple(str(v) for v in benchmark["families"])
    dev_indices=tuple(int(v) for v in benchmark["development_indices"])
    train_indices=tuple(int(v) for v in benchmark["hidden_training_indices"])
    parent_dev=evaluate_r11(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
        horizon=1,
    )
    print(json.dumps({
        "status":"R12_ACCEPTED_R11_BASELINE_FRESH_UNOPENED",
        "parent_dev_solved":parent_dev["solved"],
        "parent_dev_families":parent_dev["families"],
        "dev_indices":list(dev_indices),
    },sort_keys=True))

    candidates=[]; selected=None
    for i,cfg in enumerate(training["candidates"]):
        name=str(cfg["name"])
        torch.manual_seed(seed+i)
        model=NativeR12NeuralCausalResidualPolicy(
            copy.deepcopy(parent),
            posterior_embedding_dim=int(cfg["posterior_embedding_dim"]),
            residual_hidden_dim=int(cfg["residual_hidden_dim"]),
            max_support=int(cfg["max_support"]),
            parent_margin=float(cfg["parent_margin"]),
        )
        summary=train_r12_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            train_indices=train_indices,
            seed=seed+i,
            expert_epochs=int(cfg["expert_epochs"]),
            dagger_teacher_mix=[float(v) for v in cfg["dagger_teacher_mix"]],
            learning_rate=float(cfg["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            residual_l2_weight=float(cfg["residual_l2_weight"]),
        )
        dev=evaluate_r12(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=dev_indices,
        )
        eligibility=_eligibility(parent_dev,dev)
        rank=_rank(dev,name)
        row={
            "name":name,
            "architecture":{
                "posterior_embedding_dim":int(cfg["posterior_embedding_dim"]),
                "residual_hidden_dim":int(cfg["residual_hidden_dim"]),
                "max_support":int(cfg["max_support"]),
                "parent_margin":float(cfg["parent_margin"]),
            },
            "training":summary,
            "development":_compact(dev),
            "eligibility":eligibility,
            "rank":list(rank),
        }
        candidates.append(row)
        print(json.dumps({
            "candidate":name,
            "dev_solved":dev["solved"],
            "dev_families":dev["families"],
            "eligibility":eligibility,
            "rank":list(rank),
            "fresh_opened":False,
        },sort_keys=True))
        if eligibility["eligible"] and (selected is None or rank>selected["rank"]):
            selected={"model":model,"name":name,"dev":dev,"training":summary,"eligibility":eligibility,"rank":rank}

    predev_sha=_sha256_file(args.lock)
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    if selected is None:
        payload={
            "schema_version":1,
            "status":"R12_DEV_NO_ELIGIBLE_CANDIDATE_FRESH_UNOPENED",
            "runtime":runtime,
            "parent_development":_compact(parent_dev),
            "candidate_tournament":candidates,
            "fresh_opened":False,
        }
        args.manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
        args.dev_result.write_text(json.dumps({"parent":parent_dev,"candidates":candidates,"fresh_opened":False},indent=2,sort_keys=True)+"\n")
        return 2

    model=selected["model"]
    train_summary={
        "selected_candidate":selected["name"],
        "selected_rank":list(selected["rank"]),
        "selected_eligibility":selected["eligibility"],
        "selected_training":selected["training"],
        "parent_development":_compact(parent_dev),
        "candidate_tournament":candidates,
        "runtime":runtime,
        "fresh_opened":False,
    }
    metadata=save_r12_checkpoint(
        model,
        args.checkpoint,
        parent_checkpoint_sha256=parent_metadata["checkpoint_sha256"],
        parent_state_dict_sha256=parent_metadata["state_dict_sha256"],
        r11_authority_blob_sha=lock["accepted_r11_parent"]["accepted_authority_blob_sha"],
        predev_lock_sha256=predev_sha,
        training_summary=train_summary,
    )
    manifest={
        **metadata,
        "schema_version":1,
        "status":"R12_DEV_ELIGIBLE_FRESH_UNOPENED",
        "selected_candidate":selected["name"],
        "selected_rank":list(selected["rank"]),
        "selected_eligibility":selected["eligibility"],
        "parent_development":_compact(parent_dev),
        "dev_evaluation":_compact(selected["dev"]),
        "candidate_tournament":candidates,
        "fresh_opened":False,
    }
    args.manifest.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    args.dev_result.write_text(json.dumps(selected["dev"],indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "status":manifest["status"],
        "selected_candidate":selected["name"],
        "parent_dev_solved":parent_dev["solved"],
        "selected_dev_solved":selected["dev"]["solved"],
        "selected_dev_families":selected["dev"]["families"],
        "parameters":metadata["parameters"],
        "successor_parameters":metadata["successor_parameters"],
        "checkpoint_sha256":metadata["checkpoint_sha256"],
        "successor_state_dict_sha256":metadata["successor_state_dict_sha256"],
        "fresh_opened":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
