from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R4_ROOT = MODEL_ROOT / "neural-vnext-native-r4"
R3_ROOT = MODEL_ROOT / "neural-vnext-native-r3"
R2_ROOT = MODEL_ROOT / "neural-vnext-native-r2"
NATIVE_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R4_ROOT, R3_ROOT, R2_ROOT, NATIVE_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import evaluate_r4, load_r4_checkpoint
from belief_correction_core import NativeR8BeliefCorrectionPolicy
from belief_correction_runtime import evaluate_r8


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(family): int(row["solved"])
        for family, row in result["families"].items()
    }


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "rows"}


def _eligibility(parent: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    pf = _family_solved(parent)
    cf = _family_solved(candidate)
    visible = ("conditional_regimes", "regime_switch", "causal_prerequisites")
    visible_exact = all(cf[f] == pf[f] for f in visible)
    implicit_delta = cf["implicit_goal_regimes"] - pf["implicit_goal_regimes"]
    total_delta = int(candidate["solved"]) - int(parent["solved"])
    return {
        "eligible": bool(visible_exact and implicit_delta > 0 and total_delta > 0),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_parent": implicit_delta,
        "total_solved_delta_vs_parent": total_delta,
        "family_solved_delta_vs_parent": {f: cf[f] - pf[f] for f in pf},
    }


def _rank(result: Mapping[str, Any], name: str) -> tuple[int, int, int, str]:
    return (
        int(result["families"]["implicit_goal_regimes"]["solved"]),
        int(result["solved"]),
        -int(result["steps"]),
        str(name),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint", type=Path, default=R4_ROOT / "accepted" / "r4.pt")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("candidate") != "Neural-vNext-Native-R8-BeliefCorrection":
        raise ValueError("unexpected R8 candidate identity")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R8 fresh must remain unopened")
    if lock["benchmark"]["fresh_indices"] != [200, 239]:
        raise ValueError("R8 must reserve fresh:200..239")

    parent, metadata = load_r4_checkpoint(args.parent_checkpoint)
    if metadata["checkpoint_sha256"] != lock["parent"]["checkpoint_sha256"]:
        raise ValueError("R4 checkpoint hash mismatch")
    if metadata["state_dict_sha256"] != lock["parent"]["state_dict_sha256"]:
        raise ValueError("R4 state hash mismatch")
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    families = tuple(lock["benchmark"]["families"])
    dev_indices = tuple(lock["benchmark"]["development_indices"])
    parent_dev = evaluate_r4(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
    )
    print(json.dumps({
        "status":"R8_PARENT_BASELINE_FRESH_UNOPENED",
        "parent_dev_solved":parent_dev["solved"],
        "parent_dev_families":parent_dev["families"],
        "dev_indices":list(dev_indices),
    }, sort_keys=True))

    candidates = []
    selected = None
    for cfg in lock["selection"]["candidates"]:
        model = NativeR8BeliefCorrectionPolicy(
            copy.deepcopy(parent),
            max_support=int(cfg["max_support"]),
            correction_strength=float(cfg["correction_strength"]),
        )
        result = evaluate_r8(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=dev_indices,
        )
        eligibility = _eligibility(parent_dev, result)
        rank = _rank(result, cfg["name"])
        row = {
            "name":cfg["name"],
            "config":{
                "max_support":int(cfg["max_support"]),
                "correction_strength":float(cfg["correction_strength"]),
            },
            "development":_compact(result),
            "eligibility":eligibility,
            "rank":list(rank),
        }
        candidates.append(row)
        print(json.dumps({
            "candidate":cfg["name"],
            "dev_solved":result["solved"],
            "dev_families":result["families"],
            "eligibility":eligibility,
            "rank":list(rank),
            "correction_active_steps":result["correction_active_steps"],
            "fresh_opened":False,
        }, sort_keys=True))
        if eligibility["eligible"] and (selected is None or rank > selected["rank"]):
            selected={"row":row,"rank":rank,"result":result}

    payload = {
        "schema_version":1,
        "status":"R8_DEV_ELIGIBLE_FRESH_UNOPENED" if selected else "R8_DEV_NO_ELIGIBLE_CANDIDATE_FRESH_UNOPENED",
        "candidate":"Neural-vNext-Native-R8-BeliefCorrection",
        "parent_checkpoint_sha256":metadata["checkpoint_sha256"],
        "parent_state_dict_sha256":metadata["state_dict_sha256"],
        "predev_lock_sha256":_sha256_file(args.lock),
        "parent_development":_compact(parent_dev),
        "candidates":candidates,
        "selected_candidate":selected["row"]["name"] if selected else None,
        "selected_config":selected["row"]["config"] if selected else None,
        "selected_rank":list(selected["rank"]) if selected else None,
        "selected_eligibility":selected["row"]["eligibility"] if selected else None,
        "fresh_opened":False,
        "successor_parameters":0,
        "physical_parameters":int(lock["parent"]["parameters"]),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    args.dev_result.write_text(json.dumps({
        "parent":parent_dev,
        "selected":selected["result"] if selected else None,
        "candidates":candidates,
        "fresh_opened":False,
    }, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":payload["status"],
        "selected_candidate":payload["selected_candidate"],
        "selected_config":payload["selected_config"],
        "parent_dev_solved":parent_dev["solved"],
        "selected_dev_solved":selected["result"]["solved"] if selected else None,
        "fresh_opened":False,
    }, sort_keys=True))
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
