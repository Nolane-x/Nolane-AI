from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from typing import Sequence

import torch
from torch import Tensor
from torch.nn import functional as F

from benchmarks.codeworld.r210_copy_edit_curriculum import CopyEditTrainingRow, build_r210_training_rows
from cogcoder.r210_copy_edit_features import canonicalize_source, encode_evidence
from cogcoder.r210_copy_edit_model import (
    CopyEditProposalConfig,
    CopyEditProposalNet,
    proposal_parameter_count,
    token_ids,
)
from cogcoder.r29_patch_model import RepositorySnapshot, apply_candidate

PARENT_EFFECTIVE_PARAMETERS = 79_401_400
R210_FORMAT = 'nolane-r2.10-compact-copy-edit-proposer-v1'


@dataclass
class TrainingResult:
    config: CopyEditProposalConfig
    proposer_state: dict[str, Tensor]
    proposer_parameters: int
    train_accuracy: float
    epochs: int
    seed: int
    training_rows: int


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _row_tensors(row: CopyEditTrainingRow, *, max_length: int = 32) -> tuple[Tensor, Tensor, Tensor, int]:
    target_path = 'app.py'
    context = token_ids(canonicalize_source(row.source, language=row.language), max_length=max_length)
    snapshot = RepositorySnapshot({target_path: row.source})
    candidates: list[Tensor] = []
    for candidate in row.candidates:
        patched = apply_candidate(snapshot, candidate).files[target_path]
        candidates.append(token_ids(canonicalize_source(patched, language=row.language), max_length=max_length))
    evidence = encode_evidence(row.probes)
    return context, torch.stack(candidates), evidence, row.gold_index


def tensorize_rows(rows: Sequence[CopyEditTrainingRow]) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    materialized = [_row_tensors(row) for row in rows]
    return (
        torch.stack([item[0] for item in materialized]),
        torch.stack([item[1] for item in materialized]),
        torch.stack([item[2] for item in materialized]),
        torch.tensor([item[3] for item in materialized], dtype=torch.long),
    )


def _accuracy(model: CopyEditProposalNet, tensors: tuple[Tensor, Tensor, Tensor, Tensor], batch_size: int = 128) -> float:
    context, candidates, evidence, target = tensors
    correct = 0
    model.eval()
    with torch.no_grad():
        for start in range(0, len(target), batch_size):
            stop = start + batch_size
            c = context[start:stop]
            a = candidates[start:stop]
            e = evidence[start:stop]
            t = target[start:stop]
            mask = torch.ones(a.shape[:2], dtype=torch.bool)
            logits = model(context_tokens=c, candidate_tokens=a, evidence_features=e, candidate_mask=mask)
            correct += int((logits.argmax(dim=-1) == t).sum().item())
    return correct / max(1, len(target))


def train_copy_edit_proposer(
    *,
    seed: int = 210,
    epochs: int = 28,
    rows_per_family: int = 192,
    batch_size: int = 64,
    learning_rate: float = 3e-3,
) -> TrainingResult:
    torch.manual_seed(seed)
    rows = build_r210_training_rows(seed=seed, rows_per_family=rows_per_family)
    tensors = tensorize_rows(rows)
    model = CopyEditProposalNet(CopyEditProposalConfig())
    params = proposal_parameter_count(model)
    if params > 300_000:
        raise RuntimeError(f'R2.10 proposer exceeds parameter ceiling: {params}')
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    context, candidates, evidence, target = tensors
    generator = torch.Generator().manual_seed(seed)

    for _epoch in range(epochs):
        model.train()
        order = torch.randperm(len(target), generator=generator)
        for start in range(0, len(order), batch_size):
            index = order[start : start + batch_size]
            c = context[index]
            a = candidates[index]
            e = evidence[index]
            t = target[index]
            mask = torch.ones(a.shape[:2], dtype=torch.bool)
            logits = model(context_tokens=c, candidate_tokens=a, evidence_features=e, candidate_mask=mask)
            ce = F.cross_entropy(logits, t)
            gold = logits.gather(1, t.unsqueeze(1)).squeeze(1)
            other = logits.masked_fill(F.one_hot(t, num_classes=logits.shape[1]).bool(), float('-inf')).max(dim=1).values
            margin = F.relu(0.25 - gold + other).mean()
            loss = ce + 0.15 * margin
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

    return TrainingResult(
        config=model.config,
        proposer_state={key: value.detach().cpu() for key, value in model.state_dict().items()},
        proposer_parameters=params,
        train_accuracy=_accuracy(model, tensors),
        epochs=epochs,
        seed=seed,
        training_rows=len(rows),
    )


def save_r210_bundle(
    parent_path: Path,
    output_path: Path,
    result: TrainingResult,
    *,
    lock_sha256: str,
) -> dict[str, object]:
    parent_path = Path(parent_path)
    output_path = Path(output_path)
    parent_sha = _sha256(parent_path)
    try:
        parent_payload = torch.load(parent_path, map_location='cpu', weights_only=True)
    except Exception:
        parent_payload = {'external_parent_sha256': parent_sha}
    if not isinstance(parent_payload, dict):
        parent_payload = {'external_parent_sha256': parent_sha}
    parent_effective = int(parent_payload.get('effective_parameters', PARENT_EFFECTIVE_PARAMETERS))
    if parent_effective != PARENT_EFFECTIVE_PARAMETERS:
        raise ValueError(f'unexpected R2.10 parent parameter count: {parent_effective}')
    candidate_effective = parent_effective + result.proposer_parameters
    if candidate_effective >= 80_000_000:
        raise RuntimeError('R2.10 candidate exceeds 80M hard ceiling')

    delta = {
        'format': R210_FORMAT,
        'architecture': asdict(result.config),
        'proposer_parameters': result.proposer_parameters,
        'state': result.proposer_state,
        'training_report': {
            'seed': result.seed,
            'epochs': result.epochs,
            'training_rows': result.training_rows,
            'train_accuracy': result.train_accuracy,
            'training_language': 'python',
            'language_id_input': False,
            'task_type_id_input': False,
        },
        'pretrain_lock_sha256': lock_sha256,
    }
    payload = dict(parent_payload)
    payload.update(
        {
            'format': 'nolane-r2.10-hybrid-standalone-bundle-v1',
            'version': 'R2.10-Compact-Copy-Edit-Proposer-Phase-A-Candidate',
            'parent_r27_sha256': parent_sha,
            'parent_effective_parameters': parent_effective,
            'r210_copy_edit_delta': delta,
            'effective_parameters': candidate_effective,
            'claim_boundary_r210': (
                'Constrained copy-edit proposal only; external coding and AGI claims disabled pending locked heldout.'
            ),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output_path)
    return {
        'format': payload['format'],
        'version': payload['version'],
        'parent_sha256': parent_sha,
        'proposer_parameters': result.proposer_parameters,
        'candidate_effective_parameters': candidate_effective,
        'train_accuracy': result.train_accuracy,
        'bytes': output_path.stat().st_size,
        'sha256': _sha256(output_path),
    }


def save_r210_delta(output_path: Path, result: TrainingResult, *, lock_sha256: str) -> dict[str, object]:
    output_path = Path(output_path)
    effective = PARENT_EFFECTIVE_PARAMETERS + result.proposer_parameters
    if effective >= 80_000_000:
        raise RuntimeError('R2.10 delta exceeds 80M hard ceiling')
    delta = {
        'format': R210_FORMAT,
        'architecture': asdict(result.config),
        'proposer_parameters': result.proposer_parameters,
        'state': result.proposer_state,
        'training_report': {
            'seed': result.seed,
            'epochs': result.epochs,
            'training_rows': result.training_rows,
            'train_accuracy': result.train_accuracy,
            'training_language': 'python',
            'language_id_input': False,
            'task_type_id_input': False,
        },
        'pretrain_lock_sha256': lock_sha256,
    }
    payload = {
        'format': 'nolane-r2.10-copy-edit-delta-artifact-v1',
        'version': 'R2.10-Compact-Copy-Edit-Proposer-Phase-A-Candidate',
        'effective_parameters': effective,
        'parent_effective_parameters': PARENT_EFFECTIVE_PARAMETERS,
        'r210_copy_edit_delta': delta,
        'claim_boundary_r210': 'Constrained copy-edit proposal only; external coding and AGI claims disabled.',
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output_path)
    return {
        'proposer_parameters': result.proposer_parameters,
        'candidate_effective_parameters': effective,
        'train_accuracy': result.train_accuracy,
        'bytes': output_path.stat().st_size,
        'sha256': _sha256(output_path),
    }


def load_r210_proposer(checkpoint_path: Path) -> CopyEditProposalNet:
    payload = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    delta = payload['r210_copy_edit_delta']
    config = CopyEditProposalConfig(**delta['architecture'])
    model = CopyEditProposalNet(config)
    model.load_state_dict(delta['state'])
    model.eval()
    return model


if __name__ == '__main__':
    import argparse, json

    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lock', type=Path, default=Path('research/R2_10_PRETRAIN_LOCK.json'))
    parser.add_argument('--epochs', type=int, default=28)
    parser.add_argument('--rows-per-family', type=int, default=192)
    args = parser.parse_args()
    result = train_copy_edit_proposer(epochs=args.epochs, rows_per_family=args.rows_per_family)
    meta = save_r210_bundle(args.parent, args.output, result, lock_sha256=_sha256(args.lock))
    print(json.dumps(meta, indent=2, sort_keys=True))
