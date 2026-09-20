from __future__ import annotations
import json
from pathlib import Path
import sys,torch
HERE=Path(__file__).resolve(); ROOT=HERE.parents[1]; sys.path.insert(0,str(ROOT))
from runtime import fuse_public_with_neural_goal

def test_fusion_preserves_public_support():
    p=torch.zeros(125); p[0]=0.5; p[7]=0.5
    g=torch.full((3,5),0.2)
    f=fuse_public_with_neural_goal(p,g,alpha=1.0)
    assert torch.equal(f>0,p>0)
    assert abs(float(f.sum())-1.0)<1e-6

def test_fusion_uses_neural_mass_inside_support():
    p=torch.zeros(125); p[0]=0.5; p[1]=0.5
    g=torch.full((3,5),0.2); g[2,0]=0.8; g[2,1]=0.05
    g=g/g.sum(dim=1,keepdim=True)
    f=fuse_public_with_neural_goal(p,g,alpha=1.0)
    assert f[0]>f[1]

def test_fresh_locked():
    x=json.loads((ROOT/"PREDEV_LOCK.json").read_text())
    assert x["fresh_isolation"]["status"]=="UNOPENED"
    assert x["benchmark"]["fresh_indices"]==[280,319]
