from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import torch

from .neural_system2 import NeuralSystem2Workspace
from .r19_frontier import FrontierRolloutHead
from .r20e_executive import EvidenceEffectExecutive

FORMAT = 'nolane-r2.0i-hybrid-standalone-bundle-v1'
R19_FORMATS = {'nolane-r1.9-standalone-bundle-fp16-storage-v1', 'nolane-r1.9-standalone-bundle-v1'}
R20E_FORMAT = 'nolane-r2.0e-evidence-effect-executive-v1'
EFFECTIVE_PARAMETERS = 78_779_253


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_r20i_standalone(r19_path: str | Path, r20e_path: str | Path, output_path: str | Path, *, controller_sha256: str) -> dict[str, Any]:
    r19_path = Path(r19_path); r20e_path = Path(r20e_path); output_path = Path(output_path)
    r19 = torch.load(r19_path, map_location='cpu', weights_only=True); r20e = torch.load(r20e_path, map_location='cpu', weights_only=True)
    if not isinstance(r19, dict) or r19.get('format') not in R19_FORMATS: raise ValueError('unsupported R1.9 standalone parent format')
    if not isinstance(r20e, dict) or r20e.get('format') != R20E_FORMAT: raise ValueError('unsupported R2.0e executive format')
    r19_sha = sha256_file(r19_path)
    if r20e.get('parent_sha256') != r19_sha: raise ValueError('R2.0e is not bound to the supplied R1.9 one-weight')
    if int(r20e.get('candidate_effective_parameters', 0)) != EFFECTIVE_PARAMETERS: raise ValueError('unexpected R2.0e effective parameter count')
    payload = {'format':FORMAT,'version':'R2.0i-Active-Causal-Discovery','effective_parameters':EFFECTIVE_PARAMETERS,'new_r20i_neural_parameters':0,'controller_sha256':str(controller_sha256),'r19_parent_sha256':r19_sha,'r20e_sha256':sha256_file(r20e_path),'r19_bundle':r19,'r20e_delta':r20e,'claim_boundary':'One neural weight plus a SHA-bound public active-causal runtime. Runtime code is required for hybrid causal-discovery behavior.'}
    output_path.parent.mkdir(parents=True, exist_ok=True); torch.save(payload, output_path)
    return {'path':str(output_path),'bytes':output_path.stat().st_size,'sha256':sha256_file(output_path),'effective_parameters':EFFECTIVE_PARAMETERS,'controller_sha256':str(controller_sha256),'r19_parent_sha256':r19_sha,'r20e_sha256':payload['r20e_sha256']}


def load_r20i_standalone(path: str | Path) -> tuple[NeuralSystem2Workspace, FrontierRolloutHead, EvidenceEffectExecutive, dict[str, Any]]:
    payload = torch.load(Path(path), map_location='cpu', weights_only=True)
    if not isinstance(payload, dict) or payload.get('format') != FORMAT: raise ValueError('unsupported Nolane R2.0i standalone checkpoint format')
    r19 = payload.get('r19_bundle'); r20e = payload.get('r20e_delta')
    if not isinstance(r19, dict) or not isinstance(r20e, dict): raise ValueError('standalone bundle is missing neural components')
    parent_payload = r19.get('parent'); frontier_payload = r19.get('frontier_delta')
    if not isinstance(parent_payload, dict) or not isinstance(frontier_payload, dict): raise ValueError('R1.9 bundle is incomplete')
    parent = NeuralSystem2Workspace(**dict(parent_payload['architecture'])); parent.load_state_dict(parent_payload['model_state'], strict=True)
    rollout = FrontierRolloutHead(**dict(frontier_payload['architecture'])); rollout.load_state_dict(frontier_payload['head_state'], strict=True)
    executive = EvidenceEffectExecutive(**dict(r20e['architecture'])); executive.load_state_dict(r20e['executive_state'], strict=True)
    parent.eval(); rollout.eval(); executive.eval()
    metadata = {'version':payload.get('version'),'format':payload.get('format'),'effective_parameters':int(payload.get('effective_parameters',0)),'new_r20i_neural_parameters':int(payload.get('new_r20i_neural_parameters',0)),'controller_sha256':payload.get('controller_sha256'),'r19_parent_sha256':payload.get('r19_parent_sha256'),'r20e_sha256':payload.get('r20e_sha256'),'claim_boundary':payload.get('claim_boundary')}
    return parent, rollout, executive, metadata
