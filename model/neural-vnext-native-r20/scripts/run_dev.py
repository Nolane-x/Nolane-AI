from __future__ import annotations
import argparse,json
from pathlib import Path
import sys

HERE=Path(__file__).resolve(); ROOT=HERE.parents[1]; MODEL_ROOT=HERE.parents[2]
for p in (
 ROOT,MODEL_ROOT/"neural-vnext-native-r11",MODEL_ROOT/"neural-vnext-native-r9",
 MODEL_ROOT/"neural-vnext-native-r4",MODEL_ROOT/"neural-vnext-native-r3",
 MODEL_ROOT/"neural-vnext-native-r2",MODEL_ROOT/"neural-vnext-native",MODEL_ROOT/"r1.8",
):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from runtime import evaluate_r20

FAMILIES=("conditional_regimes","regime_switch","implicit_goal_regimes","causal_prerequisites")
VISIBLE=("conditional_regimes","regime_switch","causal_prerequisites")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--lock",type=Path,default=ROOT/"PREDEV_LOCK.json"); ap.add_argument("--parent-checkpoint",type=Path,default=MODEL_ROOT/"neural-vnext-native-r4"/"accepted"/"r4.pt"); args=ap.parse_args()
    lock=json.loads(args.lock.read_text()); assert lock["fresh_isolation"]["status"]=="UNOPENED"; assert lock["benchmark"]["fresh_indices"]==[280,319]
    parent,meta=load_r4_checkpoint(args.parent_checkpoint)
    baseline=evaluate_r11(parent,make_task=make_r18_task,families=FAMILIES,split="dev",indices=tuple(lock["benchmark"]["development_indices"]),horizon=1)
    rows=[]
    for c in lock["selection"]["candidates"]:
        ev=evaluate_r20(
            parent,make_task=make_r18_task,families=FAMILIES,split="dev",
            indices=tuple(lock["benchmark"]["development_indices"]),
            max_probes=c["max_probes"],max_probe_step=c["max_probe_step"],
            minimum_budget_remaining=c["minimum_budget_remaining"],
        )
        fd={f:int(ev["families"][f]["solved"])-int(baseline["families"][f]["solved"]) for f in FAMILIES}
        eligible=int(ev["solved"])>int(baseline["solved"]) and fd["implicit_goal_regimes"]>=1 and all(fd[f]==0 for f in VISIBLE)
        rows.append({"name":c["name"],"config":c,"evaluation":ev,"family_solved_delta_vs_parent":fd,"total_solved_delta_vs_parent":int(ev["solved"])-int(baseline["solved"]),"eligible":bool(eligible)})
    es=[r for r in rows if r["eligible"]]
    selected=max(es,key=lambda r:(r["family_solved_delta_vs_parent"]["implicit_goal_regimes"],r["total_solved_delta_vs_parent"],-r["evaluation"]["steps"],r["name"]),default=None)
    args.output.mkdir(parents=True,exist_ok=True)
    manifest={"status":"R20_DEV_ELIGIBLE_FRESH_UNOPENED" if selected else "R20_DEV_REJECTED_FRESH_UNOPENED","fresh_opened":False,"parent_checkpoint_sha256":meta["checkpoint_sha256"],"parent_state_dict_sha256":meta["state_dict_sha256"],"successor_parameters":0,"physical_parameters":877542,"parent_development":baseline,"candidates":rows,"selected_candidate":None if selected is None else selected["name"],"selected_config":None if selected is None else selected["config"]}
    (args.output/"r20.dev.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":manifest["status"],"parent_dev_solved":baseline["solved"],"selected_candidate":manifest["selected_candidate"],"selected_dev_solved":None if selected is None else selected["evaluation"]["solved"],"candidates":[{"name":r["name"],"solved":r["evaluation"]["solved"],"implicit":r["evaluation"]["families"]["implicit_goal_regimes"]["solved"],"probes":r["evaluation"]["probes"],"overrides":r["evaluation"]["overrides_vs_r11"],"delta":r["total_solved_delta_vs_parent"],"family_delta":r["family_solved_delta_vs_parent"],"eligible":r["eligible"]} for r in rows],"fresh_opened":False},sort_keys=True))
if __name__=="__main__": main()
