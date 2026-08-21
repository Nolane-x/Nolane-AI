from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import nn

from cogcoder.neural_system2 import NeuralSystem2Workspace
from cogcoder.r19_frontier import FrontierRolloutHead
from cogcoder.r20e_executive import EvidenceEffectExecutive
from cogcoder.r21_causal_router import CausalEvidenceRouter
from r23.ultra_core import ScaledRecursiveDistilledReasoner

FORMAT = 'nolane-neural-r2.3-ultra-recursive-physical-one-weight-v1'


def physical_parameter_count(*modules: nn.Module) -> int:
    return sum(p.numel() for module in modules for p in module.parameters())


def load_r23_one_weight(path: str | Path):
    payload = torch.load(Path(path), map_location='cpu', weights_only=True)
    if not isinstance(payload, dict) or payload.get('format') != FORMAT:
        raise ValueError('unsupported Neural R2.3 bundle')
    parent_bundle = payload['r21a_parent_bundle']
    if parent_bundle.get('format') != 'nolane-neural-r2.1a-causal-evidence-router-one-weight-v1':
        raise ValueError('unsupported embedded Neural R2.1a parent')
    r20 = parent_bundle['r20i_bundle']; r21a = parent_bundle['r21a_delta']; r19 = r20['r19_bundle']; r20e = r20['r20e_delta']
    parent_payload = r19['parent']; frontier_payload = r19['frontier_delta']
    parent = NeuralSystem2Workspace(**dict(parent_payload['architecture'])); parent.load_state_dict(parent_payload['model_state'], strict=True)
    rollout = FrontierRolloutHead(**dict(frontier_payload['architecture'])); rollout.load_state_dict(frontier_payload['head_state'], strict=True)
    executive = EvidenceEffectExecutive(**dict(r20e['architecture'])); executive.load_state_dict(r20e['executive_state'], strict=True)
    router = CausalEvidenceRouter(**dict(r21a['architecture'])); router.load_state_dict(r21a['state_dict'], strict=True)
    delta = payload['r23_ultra_delta']
    reasoner = ScaledRecursiveDistilledReasoner(**dict(delta['architecture'])); reasoner.load_state_dict({k: v.float() for k, v in delta['state_dict'].items()}, strict=True)
    for module in (parent, rollout, executive, router, reasoner): module.eval()
    meta: dict[str, Any] = {k: v for k, v in payload.items() if k not in {'r21a_parent_bundle','r23_ultra_delta'}}
    count = physical_parameter_count(parent, rollout, executive, router, reasoner)
    if count != int(meta['physical_parameters']):
        raise ValueError(f'physical parameter audit mismatch: {count} != {meta["physical_parameters"]}')
    return parent, rollout, executive, router, reasoner, meta
