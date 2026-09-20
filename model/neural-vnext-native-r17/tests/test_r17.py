from __future__ import annotations
import json
from pathlib import Path
import sys
import torch
HERE=Path(__file__).resolve(); ROOT=HERE.parents[1]; sys.path.insert(0,str(ROOT))
from world_model import PublicDynamicsNet,ensemble_predictions
from runtime import _future_global

def test_model_and_future_state_encoding():
    m=PublicDynamicsNet(hidden_dim=64)
    logits=m(torch.zeros(2,29),torch.zeros(2,4,25))
    assert logits.shape==(2,4,3,5)
    g=torch.zeros(29); s=torch.tensor([4,3,2])
    f=_future_global(g,s,2)
    assert torch.allclose(f[0:3],torch.tensor([1.0,0.75,0.5]))
    assert torch.equal(f[3:6],torch.tensor([0.0,1.0,0.0]))

def test_ensemble_shapes():
    torch.manual_seed(3); a=PublicDynamicsNet(64)
    torch.manual_seed(4); b=PublicDynamicsNet(64)
    p,agree,conf=ensemble_predictions([a,b],torch.zeros(1,29),torch.zeros(1,4,25))
    assert p.shape==(1,4,3) and agree.shape==(1,4) and conf.shape==(1,4)

def test_fresh_locked():
    lock=json.loads((ROOT/"PREDEV_LOCK.json").read_text())
    assert lock["fresh_isolation"]["status"]=="UNOPENED"
    assert lock["benchmark"]["fresh_indices"]==[280,319]
    assert lock["confirmation"]["status"]=="PREREGISTERED_UNOPENED"
