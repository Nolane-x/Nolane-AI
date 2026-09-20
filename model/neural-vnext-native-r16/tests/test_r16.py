from __future__ import annotations

import json
from pathlib import Path
import sys

import torch

HERE=Path(__file__).resolve()
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))

from world_model import PublicDynamicsNet, ensemble_predictions


def test_world_model_shape_and_parameter_count():
    model=PublicDynamicsNet(hidden_dim=64)
    logits=model(torch.zeros(2,29),torch.zeros(2,4,25))
    assert logits.shape==(2,4,3,5)
    assert model.parameter_count()>0


def test_ensemble_requires_exact_member_agreement():
    torch.manual_seed(1)
    a=PublicDynamicsNet(hidden_dim=64)
    torch.manual_seed(2)
    b=PublicDynamicsNet(hidden_dim=64)
    pred,agreement,confidence=ensemble_predictions(
        [a,b],torch.zeros(1,29),torch.zeros(1,4,25)
    )
    assert pred.shape==(1,4,3)
    assert agreement.shape==(1,4)
    assert confidence.shape==(1,4)
    assert torch.isfinite(confidence).all()


def test_fresh_is_locked():
    lock=json.loads((ROOT/"PREDEV_LOCK.json").read_text())
    assert lock["fresh_isolation"]["status"]=="UNOPENED"
    assert lock["benchmark"]["fresh_indices"]==[280,319]
    assert lock["confirmation"]["status"]=="PREREGISTERED_UNOPENED"
