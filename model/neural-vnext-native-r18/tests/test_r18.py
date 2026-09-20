from __future__ import annotations
import json
from pathlib import Path
import sys,torch
HERE=Path(__file__).resolve(); ROOT=HERE.parents[1]; sys.path.insert(0,str(ROOT))
from world_model import PublicDynamicsNet
from runtime import _future_global
def test_shapes():
    m=PublicDynamicsNet(64); assert m(torch.zeros(1,29),torch.zeros(1,4,25)).shape==(1,4,3,5)
    f=_future_global(torch.zeros(29),torch.tensor([1,2,3]),1); assert torch.equal(f[3:6],torch.tensor([1.,0.,1.]))
def test_fresh_locked():
    x=json.loads((ROOT/"PREDEV_LOCK.json").read_text()); assert x["fresh_isolation"]["status"]=="UNOPENED"; assert x["benchmark"]["fresh_indices"]==[280,319]
