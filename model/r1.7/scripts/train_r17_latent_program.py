from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import torch

from cogcoder.r17_program_training import (
    ProgramTrainingRow,
    evaluate_program_rows,
    latent_program_internal_gate,
    latent_program_trainable_parameter_names,
    train_program_epoch,
)
from cogcoder.r17_training import checkpoint_metadata_for_report, load_r17_checkpoint, save_r17_checkpoint, sha256_file


def _load_rows(paths):
    rows = []
    for path in paths:
        for item in torch.load(path, map_location='cpu', weights_only=False):
            rows.append(ProgramTrainingRow(**item))
    return rows


def main() -> None:
    seed = 170817
    epochs = 60
    lr = 1e-3
    torch.manual_seed(seed)
    random.seed(seed)
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[1]
    r12 = root / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    r16 = root / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'
    parent = root / 'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt'
    model, parent_meta = load_r17_checkpoint(parent, expected_r1_2_checkpoint=r12, expected_r1_6_parent_checkpoint=r16)
    cache_paths = [root / f'cache/r17_program/chunk-{start}.pt' for start in (218, 234, 250, 266)]
    all_rows = _load_rows(cache_paths)
    fit_rows = [row for row in all_rows if row.template_id in {0,1,2,3,4,5}]
    val_rows = [row for row in all_rows if row.template_id in {6,7}]
    assert fit_rows and val_rows
    assert set(row.template_id for row in fit_rows) == {0,1,2,3,4,5}
    assert set(row.template_id for row in val_rows) == {6,7}

    for parameter in model.parameters():
        parameter.requires_grad_(False)
    names = set(latent_program_trainable_parameter_names(model))
    params = []
    for name, parameter in model.named_parameters():
        if name in names:
            parameter.requires_grad_(True)
            params.append(parameter)
    assert sum(parameter.numel() for parameter in params) == 53_761
    optimizer = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)

    initial = evaluate_program_rows(model, val_rows)
    best = initial
    best_epoch = 0
    best_state = copy.deepcopy(model.state_dict())
    history = []
    print(json.dumps({'event':'precompute','all_rows':len(all_rows),'fit_rows':len(fit_rows),'val_rows':len(val_rows),'initial':initial}, sort_keys=True), flush=True)
    for epoch in range(1, epochs + 1):
        loss = train_program_epoch(model, fit_rows, optimizer)
        metrics = evaluate_program_rows(model, val_rows)
        history.append({'epoch': epoch, 'train_loss': loss, **metrics})
        print(json.dumps({'epoch':epoch,'train_loss':loss,**metrics}, sort_keys=True), flush=True)
        if latent_program_internal_gate(metrics) and (best_epoch == 0 or metrics['candidate_operation_accuracy'] > best['candidate_operation_accuracy']):
            best = copy.deepcopy(metrics)
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())

    model.load_state_dict(best_state)
    accepted = best_epoch > 0 and latent_program_internal_gate(best)
    report = {
        'version':'r1.7-latent-program-internal-v1',
        'protocol':{
            'world_indices':[218,282],
            'fit_templates':[0,1,2,3,4,5],
            'val_templates':[6,7],
            'seed':seed,'epochs':epochs,'lr':lr,'weight_decay':1e-4,
        },
        'parent_sha256':sha256_file(parent),
        'parent_candidate_effective_parameters':parent_meta['candidate_effective_parameters'],
        'trainable_parameters':sum(p.numel() for p in params),
        'fit_rows':len(fit_rows),'val_rows':len(val_rows),
        'initial_validation':initial,'best_epoch':best_epoch,'best_validation':best,
        'accepted_for_policy_integration':accepted,'history':history,
    }
    result = root / 'results/r1_7_latent_program_internal.json'
    result.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    if not accepted:
        print(json.dumps({'accepted':False,'best_epoch':best_epoch,'best':best}, sort_keys=True), flush=True)
        raise SystemExit(2)
    meta = save_r17_checkpoint(root / 'checkpoints/Nolane-R1.7-NCPM-LatentProgram.pt', model, r1_2_checkpoint=r12, r1_6_parent_checkpoint=r16, report={'phase':'latent-program-template-holdout','internal_gate':best})
    report['checkpoint'] = checkpoint_metadata_for_report(meta)
    result.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'accepted':True,'best_epoch':best_epoch,'best':best,'checkpoint':report['checkpoint']}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
