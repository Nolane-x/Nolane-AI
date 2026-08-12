from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

import torch

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_goal_training import (
    collect_goal_difference_episode,
    evaluate_goal_difference_episodes,
    goal_difference_internal_gate,
    goal_difference_parent_provenance,
    goal_difference_trainable_parameter_names,
    train_goal_difference_epoch,
)
from cogcoder.r17_training import (
    checkpoint_metadata_for_report,
    load_r17_checkpoint,
    save_r17_checkpoint,
)

FAMILIES = ("causal_laws", "causal_switch")


def _collect(model, start: int, count: int, *, exploration_steps: int, max_steps: int):
    episodes = []
    for family in FAMILIES:
        for index in range(start, start + count):
            episodes.append(
                collect_goal_difference_episode(
                    model,
                    make_r17_task(family, "train", index),
                    exploration_steps=exploration_steps,
                    max_steps=max_steps,
                )
            )
    return episodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--fit-start", type=int, default=56)
    parser.add_argument("--fit-count", type=int, default=16)
    parser.add_argument("--val-start", type=int, default=72)
    parser.add_argument("--val-count", type=int, default=8)
    parser.add_argument("--exploration-steps", type=int, default=6)
    parser.add_argument("--max-steps", type=int, default=14)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=170317)
    parser.add_argument(
        "--parent", default="checkpoints/Nolane-R1.7-NCPM-CausalLaws.pt"
    )
    parser.add_argument(
        "--output", default="checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt"
    )
    parser.add_argument(
        "--result", default="results/r1_7_goal_difference_internal.json"
    )
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    root = Path(__file__).resolve().parents[1]
    r12 = root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt"
    r16 = root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt"
    law_parent = root / args.parent
    model, law_meta = load_r17_checkpoint(
        law_parent,
        expected_r1_2_checkpoint=r12,
        expected_r1_6_parent_checkpoint=r16,
    )
    law_provenance = goal_difference_parent_provenance(law_parent, law_meta)

    trainable_names = set(
        goal_difference_trainable_parameter_names(model, include_policy_scale=False)
    )
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name in trainable_names)
    assert not model.goal_difference_policy_scale.requires_grad
    assert float(model.goal_difference_policy_scale.detach()) == 0.0

    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=args.lr,
        weight_decay=1e-4,
    )

    t0 = time.time()
    fit = _collect(
        model,
        args.fit_start,
        args.fit_count,
        exploration_steps=args.exploration_steps,
        max_steps=args.max_steps,
    )
    val = _collect(
        model,
        args.val_start,
        args.val_count,
        exploration_steps=args.exploration_steps,
        max_steps=args.max_steps,
    )
    initial = evaluate_goal_difference_episodes(model, val)
    best_state = copy.deepcopy(model.state_dict())
    best = initial
    best_epoch = 0
    history = []
    print(
        json.dumps(
            {
                "event": "precompute",
                "fit_episodes": len(fit),
                "val_episodes": len(val),
                "seconds": time.time() - t0,
                "initial": initial,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    for epoch in range(1, args.epochs + 1):
        loss = train_goal_difference_epoch(model, fit, optimizer)
        metrics = evaluate_goal_difference_episodes(model, val)
        row = {"epoch": epoch, "train_loss": loss, **metrics}
        history.append(row)
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_loss": loss,
                    "candidate_mse": metrics["candidate_mse"],
                    "baseline_mse": metrics["baseline_mse"],
                    "relative_improvement": metrics["relative_improvement"],
                    "families": metrics["families"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if (
            goal_difference_internal_gate(metrics)
            and metrics["candidate_mse"] < best["candidate_mse"]
        ):
            best = metrics
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())

    model.load_state_dict(best_state)
    accepted = best_epoch > 0 and goal_difference_internal_gate(best)
    report: dict[str, object] = {
        "version": "r1.7-goal-difference-internal-v1",
        "protocol": {
            "fit": [args.fit_start, args.fit_start + args.fit_count],
            "val": [args.val_start, args.val_start + args.val_count],
            "families": list(FAMILIES),
            "seed": args.seed,
            "exploration_steps": args.exploration_steps,
            "max_steps": args.max_steps,
            "epochs": args.epochs,
            "lr": args.lr,
        },
        "law_parent_sha256": law_provenance["sha256"],
        "law_parent_candidate_effective_parameters": law_provenance["candidate_effective_parameters"],
        "trainable_parameters": sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        ),
        "trainable_names": sorted(trainable_names),
        "goal_difference_policy_scale": float(
            model.goal_difference_policy_scale.detach()
        ),
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best,
        "accepted_for_policy_calibration": accepted,
        "history": history,
    }
    result_path = root / args.result
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    if not accepted:
        print(
            json.dumps(
                {"accepted": False, "best_epoch": best_epoch, "best": best},
                sort_keys=True,
            ),
            flush=True,
        )
        raise SystemExit(2)

    if float(model.goal_difference_policy_scale.detach()) != 0.0:
        raise RuntimeError("Goal-Difference world-model gate must keep policy scale zero")
    meta = save_r17_checkpoint(
        root / args.output,
        model,
        r1_2_checkpoint=r12,
        r1_6_parent_checkpoint=r16,
        report={
            "phase": "goal-difference-world-model",
            "law_parent_sha256": law_provenance["sha256"],
            "internal_gate": best,
        },
    )
    report["checkpoint"] = checkpoint_metadata_for_report(meta)
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "accepted": True,
                "best_epoch": best_epoch,
                "best": best,
                "checkpoint": checkpoint_metadata_for_report(meta),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
