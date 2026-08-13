from __future__ import annotations

from pathlib import Path

from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r19_standalone import load_r19_standalone
from cogcoder.r20e_training import load_r20e_checkpoint
from cogcoder.r20i_causal_discovery import run_r20i_episode

ROOT=Path(__file__).resolve().parents[1]
R19=ROOT/'checkpoints/Nolane-R1.9-78M-STRONGEST-ONE-WEIGHT-FP16.pt'
R20E=ROOT/'checkpoints/Nolane-R2.0e-RIE-EvidenceEffect.pt'

def test_one_weight_build_and_loader_reproduce_hybrid_smoke(tmp_path):
    from cogcoder.r20i_standalone import build_r20i_standalone,load_r20i_standalone
    out=tmp_path/'nolane-r20i-one-weight.pt';meta=build_r20i_standalone(R19,R20E,out,controller_sha256='cc254838dd42e1081e888619f71276a3d1af1cf7ba0a55af7796ddbf39eec672');assert meta['effective_parameters']==78_779_253
    original_parent,original_rollout,_=load_r19_standalone(R19);original_executive,_=load_r20e_checkpoint(R20E,expected_parent_path=R19);loaded_parent,loaded_rollout,loaded_executive,loaded_meta=load_r20i_standalone(out);assert loaded_meta['effective_parameters']==78_779_253
    for family,index in [('conditional_regimes',2100),('causal_prerequisites',2101)]:
        a=run_r20i_episode(original_parent,original_rollout,original_executive,make_r18_task(family,'train',index),mode='hybrid_active_causal');b=run_r20i_episode(loaded_parent,loaded_rollout,loaded_executive,make_r18_task(family,'train',index),mode='hybrid_active_causal');assert a['actions']==b['actions'];assert a['solved']==b['solved']

def test_loader_rejects_wrong_format(tmp_path):
    import torch
    from cogcoder.r20i_standalone import load_r20i_standalone
    bad=tmp_path/'bad.pt';torch.save({'format':'wrong'},bad)
    try: load_r20i_standalone(bad)
    except ValueError as exc: assert 'unsupported' in str(exc)
    else: raise AssertionError('bad format must fail')
