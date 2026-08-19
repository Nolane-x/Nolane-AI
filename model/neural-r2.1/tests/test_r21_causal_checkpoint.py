from __future__ import annotations
from pathlib import Path
import pytest,torch
from cogcoder.r21_causal_checkpoint import R20I_EFFECTIVE_PARAMETERS,build_r21a_one_weight,load_r21a_delta,save_r21a_delta
from cogcoder.r21_causal_router import CausalEvidenceRouter

def _p(path:Path,marker=1.):torch.save({'format':'nolane-r2.0i-hybrid-standalone-bundle-v1','effective_parameters':R20I_EFFECTIVE_PARAMETERS,'marker':torch.tensor(marker)},path);return path

def test_roundtrip_and_bundle(tmp_path:Path):
 p=_p(tmp_path/'p.pt');d=tmp_path/'d.pt';m=save_r21a_delta(d,CausalEvidenceRouter(),parent_checkpoint=p);assert m['delta_parameters']==120151 and m['candidate_effective_parameters']==78899404;_,meta=load_r21a_delta(d,expected_parent_checkpoint=p);assert meta['candidate_effective_parameters']==78899404;out=tmp_path/'one.pt';assert build_r21a_one_weight(p,d,out)['effective_parameters']==78899404

def test_wrong_parent_fails_closed(tmp_path:Path):
 p=_p(tmp_path/'p.pt',1.);q=_p(tmp_path/'q.pt',2.);d=tmp_path/'d.pt';save_r21a_delta(d,CausalEvidenceRouter(),parent_checkpoint=p)
 with pytest.raises(ValueError,match='parent checkpoint SHA-256 mismatch'):load_r21a_delta(d,expected_parent_checkpoint=q)
