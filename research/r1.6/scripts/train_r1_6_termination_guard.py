from __future__ import annotations

import argparse
import hashlib
import random
from pathlib import Path

import torch
import torch.nn.functional as F

from cogcoder.frontier_interactive import build_split
from cogcoder.neural_system2_curriculum import (
    FrozenStage2ObservationEncoder,
    _flat_batch_tensors,
    _flat_steps,
    collect_teacher_trajectories,
)
from cogcoder.neural_system2_training import load_system2_checkpoint, save_system2_checkpoint
from cogcoder.edit_training import load_stage2_checkpoint


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--per-family', type=int, default=20)
    ap.add_argument('--epochs', type=int, default=120)
    ap.add_argument('--seed', type=int, default=1606)
    args = ap.parse_args()
    torch.manual_seed(args.seed)
    random.seed(args.seed)

    root = Path(__file__).resolve().parents[1]
    r12 = root / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    parent = root / 'checkpoints/Nolane-R1.6-NS2-CounterfactualWorld.pt'
    model, _ = load_system2_checkpoint(parent, expected_r1_2_checkpoint=r12)
    model.eval()

    trunk, tokenizer, _ = load_stage2_checkpoint(root / 'checkpoints/Nolane-48M-Stage2-Policy.pt')
    encoder = FrozenStage2ObservationEncoder(trunk, tokenizer, max_length=96)
    trajectories = collect_teacher_trajectories(build_split('train', per_family=args.per_family), encoder)
    steps = _flat_steps(trajectories)
    batch = _flat_batch_tensors(steps, device=torch.device('cpu'))

    captured: dict[str, torch.Tensor] = {}
    def ready_hook(_module, inputs):
        captured['thought'] = inputs[0].detach().clone()
    def terminal_hook(_module, inputs):
        captured['actions'] = inputs[0].detach().clone()
    h1 = model.readiness_head[0].register_forward_pre_hook(ready_hook)
    h2 = model.termination_head[0].register_forward_pre_hook(terminal_hook)
    with torch.no_grad():
        model(
            batch['latents'], batch['action_tokens'], legal_mask=batch['legal'],
            observation_tokens=batch['observation_tokens'],
            structured_ids=batch['structured_ids'], structured_values=batch['structured_values'],
            refinement_steps=1, policy_mode='full',
        )
    h1.remove(); h2.remove()
    thought = captured['thought']
    actions = captured['actions']
    readiness_target = batch['readiness']
    done_target = batch['counterfactual_done']
    legal = batch['legal']

    for p in model.parameters():
        p.requires_grad = False
    for module in (model.readiness_head, model.termination_head):
        for p in module.parameters():
            p.requires_grad = True
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=2e-3, weight_decay=1e-4)
    best = (1e9, None)
    for epoch in range(1, args.epochs + 1):
        opt.zero_grad(set_to_none=True)
        ready = torch.sigmoid(model.readiness_head(thought).squeeze(-1))
        terminal = torch.sigmoid(model.termination_head(actions).squeeze(-1))
        ready_loss = F.binary_cross_entropy(ready, readiness_target)
        terminal_loss = F.binary_cross_entropy(terminal[legal], done_target[legal])
        loss = 0.65 * ready_loss + 0.35 * terminal_loss
        loss.backward(); opt.step()
        value = float(loss.detach())
        if value < best[0]:
            best = (value, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
        if epoch in {1, 10, 20, 40, 80, args.epochs}:
            ready_acc = float(((ready >= 0.5) == (readiness_target >= 0.5)).float().mean())
            term_acc = float(((terminal[legal] >= 0.5) == (done_target[legal] >= 0.5)).float().mean())
            print({'epoch': epoch, 'loss': value, 'readiness_accuracy': ready_acc, 'terminal_accuracy': term_acc}, flush=True)
    assert best[1] is not None
    model.load_state_dict(best[1])
    out = root / 'checkpoints/Nolane-R1.6-NS2-TerminationGuard.pt'
    meta = save_system2_checkpoint(
        out, model, r1_2_checkpoint=r12,
        report={
            'experiment': 'factorized-termination-guard',
            'parent': parent.name,
            'train_tasks': args.per_family * 3,
            'train_steps': len(steps),
            'best_cached_loss': best[0],
            'fresh_opened': False,
        },
    )
    print({'saved': str(out), 'sha256': meta['sha256'], 'candidate_effective_parameters': meta['candidate_effective_parameters']}, flush=True)


if __name__ == '__main__':
    main()
