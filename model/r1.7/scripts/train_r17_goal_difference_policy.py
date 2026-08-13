from __future__ import annotations

import argparse
import copy
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F

from cogcoder.edit_training import load_stage2_checkpoint
from cogcoder.neural_system2 import CausalLawState, encode_structured_observation
from cogcoder.neural_system2_curriculum import FrozenStage2ObservationEncoder
from cogcoder.r17_goal_training import goal_difference_policy_trainable_parameter_names
from cogcoder.r17_training import checkpoint_metadata_for_report, load_r17_checkpoint, save_r17_checkpoint
from train_r17_causal_law_policy import _cache_rows, _select


@dataclass
class GoalPolicyRow:
    family: str
    base_logits: torch.Tensor
    predicted_progress: torch.Tensor
    label: int


def _cache_goal_rows(model, episodes, encoder):
    law_rows = _cache_rows(model, episodes, encoder)
    raw_steps = [(episode, step) for episode in episodes for step in episode.steps]
    if len(law_rows) != len(raw_steps):
        raise RuntimeError("cached policy rows do not align with raw teacher steps")
    rows: list[GoalPolicyRow] = []
    model.eval()
    with torch.no_grad():
        for law_row, (episode, step) in zip(law_rows, raw_steps):
            ids, values = encode_structured_observation(step.text, max_atoms=96)
            ids = ids.unsqueeze(0)
            values = values.unsqueeze(0)
            atoms, mask = model.structured_observation_encoder.encode_atoms(ids, values)
            law = CausalLawState(
                slots=law_row.law_slots.unsqueeze(0),
                confidence=law_row.law_confidence.unsqueeze(0),
                usage=law_row.law_usage.unsqueeze(0),
            )
            state = law_row.state_sketch.unsqueeze(0)
            actions = law_row.enriched_actions.unsqueeze(0)
            law_scores = model.causal_law_scores(state, actions, law)
            goal = model.goal_difference_scores(
                atoms,
                mask,
                law_scores["predicted_delta"],
                actions,
                law_scores["confidence"],
            )
            rows.append(
                GoalPolicyRow(
                    family=episode.family,
                    base_logits=law_row.base_logits.clone(),
                    predicted_progress=goal["predicted_progress"][0].cpu(),
                    label=int(law_row.label),
                )
            )
    return rows


def _groups(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(row.base_logits.shape[0])].append(row)
    return grouped


def _objective(scale: torch.Tensor, grouped):
    losses = []
    correct = 0
    total = 0
    family = defaultdict(lambda: [0, 0])
    weight = torch.tanh(scale)
    for _, items in grouped.items():
        base = torch.stack([row.base_logits for row in items])
        progress = torch.stack([row.predicted_progress for row in items])
        labels = torch.tensor([row.label for row in items], dtype=torch.long)
        logits = base + weight * progress
        losses.append(F.cross_entropy(logits, labels))
        pred = logits.argmax(-1)
        correct += int(pred.eq(labels).sum())
        total += len(items)
        for i, row in enumerate(items):
            family[row.family][0] += int(pred[i].item() == row.label)
            family[row.family][1] += 1
    return torch.stack(losses).mean(), {
        "accuracy": correct / max(1, total),
        "rows": total,
        "family": {name: c / n for name, (c, n) in family.items()},
    }


def _causal_score(metrics):
    family = metrics["family"]
    return (family.get("causal_laws", 0.0) + family.get("causal_switch", 0.0)) / 2.0


def _preservation_score(metrics):
    family = metrics["family"]
    return (family.get("goal_inference", 0.0) + family.get("composition_holdout", 0.0)) / 2.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-start", type=int, default=80)
    parser.add_argument("--fit-count", type=int, default=12)
    parser.add_argument("--val-start", type=int, default=92)
    parser.add_argument("--val-count", type=int, default=4)
    parser.add_argument("--exploration-steps", type=int, default=6)
    parser.add_argument("--max-steps", type=int, default=14)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=170417)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    root = Path(__file__).resolve().parents[1]
    r12 = root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt"
    r16 = root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt"
    goal_checkpoint = root / "checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt"
    model, _ = load_r17_checkpoint(
        goal_checkpoint,
        expected_r1_2_checkpoint=r12,
        expected_r1_6_parent_checkpoint=r16,
    )
    trunk, tokenizer, _ = load_stage2_checkpoint(root / "checkpoints/Nolane-48M-Stage2-Policy.pt")
    encoder = FrozenStage2ObservationEncoder(trunk, tokenizer, max_length=96)

    fit_episodes = _select(args.fit_start, args.fit_count, exploration_steps=args.exploration_steps, max_steps=args.max_steps)
    val_episodes = _select(args.val_start, args.val_count, exploration_steps=args.exploration_steps, max_steps=args.max_steps)
    fit_groups = _groups(_cache_goal_rows(model, fit_episodes, encoder))
    val_groups = _groups(_cache_goal_rows(model, val_episodes, encoder))

    for parameter in model.parameters():
        parameter.requires_grad_(False)
    names = goal_difference_policy_trainable_parameter_names(model)
    assert names == ["goal_difference_policy_scale"]
    scale = dict(model.named_parameters())["goal_difference_policy_scale"]
    scale.requires_grad_(True)
    optimizer = torch.optim.Adam([scale], lr=args.lr)

    with torch.no_grad():
        base_loss, base = _objective(scale, val_groups)
    best_loss = float(base_loss)
    best_epoch = 0
    best_scale = scale.detach().clone()
    best_metrics = base
    history = []

    for epoch in range(1, args.epochs + 1):
        optimizer.zero_grad(set_to_none=True)
        loss, fit_metrics = _objective(scale, fit_groups)
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            val_loss, val_metrics = _objective(scale, val_groups)
        row = {
            "epoch": epoch,
            "fit_loss": float(loss.detach()),
            "val_loss": float(val_loss),
            "fit": fit_metrics,
            "val": val_metrics,
            "scale": float(torch.tanh(scale).detach()),
        }
        history.append(row)
        valid = (
            float(val_loss) < float(base_loss)
            and val_metrics["accuracy"] >= base["accuracy"]
            and _causal_score(val_metrics) > _causal_score(base)
            and _preservation_score(val_metrics) >= _preservation_score(base)
        )
        if valid and float(val_loss) < best_loss:
            best_loss = float(val_loss)
            best_epoch = epoch
            best_scale = scale.detach().clone()
            best_metrics = copy.deepcopy(val_metrics)

    with torch.no_grad():
        scale.copy_(best_scale)
    accepted = best_epoch > 0
    report = {
        "version": "r1.7-goal-difference-policy-internal-v1",
        "protocol": vars(args),
        "base_loss": float(base_loss),
        "base_metrics": base,
        "best_epoch": best_epoch,
        "best_loss": best_loss,
        "best_metrics": best_metrics,
        "accepted_for_dev": accepted,
        "trainable_parameters": 1,
        "scale": float(torch.tanh(scale).detach()),
        "history": history,
    }
    result = root / "results/r1_7_goal_difference_policy_internal.json"
    result.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if not accepted:
        print(json.dumps(report, sort_keys=True), flush=True)
        raise SystemExit(2)
    meta = save_r17_checkpoint(
        root / "checkpoints/Nolane-R1.7-NCPM-GoalDifferencePolicy.pt",
        model,
        r1_2_checkpoint=r12,
        r1_6_parent_checkpoint=r16,
        report={"goal_difference_policy_internal": report},
    )
    report["checkpoint"] = checkpoint_metadata_for_report(meta)
    result.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"accepted": True, "best_epoch": best_epoch, "best_loss": best_loss, "best_metrics": best_metrics, "scale": report["scale"], "checkpoint": report["checkpoint"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
