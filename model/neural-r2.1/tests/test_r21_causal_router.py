from __future__ import annotations
import torch
from cogcoder.r21_causal_router import CausalEvidenceRouter,r21a_parameter_count

def _x(b=2,a=6):
 g=torch.Generator().manual_seed(211);return {'state':torch.randn(b,128,generator=g),'context':torch.randn(b,64,generator=g),'action_embeddings':torch.randn(b,a,640,generator=g),'parent_effects':torch.randn(b,a,128,generator=g),'imagined_effects':torch.randn(b,a,128,generator=g),'evidence_effects':torch.randn(b,a,128,generator=g),'action_memory':torch.randn(b,a,7,generator=g),'imagined_uncertainty':torch.rand(b,a,generator=g),'imagined_value':torch.randn(b,a,generator=g),'base_action_logits':torch.randn(b,a,generator=g),'progress':torch.rand(b,1,generator=g),'budget_fraction':torch.rand(b,1,generator=g),'previous_feedback':torch.randn(b,3,generator=g)}

def test_budget_noop_and_shapes():
 torch.manual_seed(21);m=CausalEvidenceRouter().eval();x=_x();o=m(**x);assert r21a_parameter_count(m)==120151;torch.testing.assert_close(o['action_logits'],x['base_action_logits'],rtol=0,atol=0);assert o['role_logits'].shape==(2,6,5);assert o['router_activation'].shape==(2,)

def test_permutation_equivariance():
 torch.manual_seed(21);m=CausalEvidenceRouter().eval();x=_x();a=m(**x);order=torch.tensor([4,0,5,2,1,3]);y=dict(x)
 for k in ('action_embeddings','parent_effects','imagined_effects','evidence_effects','action_memory','imagined_uncertainty','imagined_value','base_action_logits'):y[k]=x[k][:,order]
 b=m(**y);torch.testing.assert_close(b['action_logits'],a['action_logits'][:,order],rtol=1e-5,atol=1e-6);torch.testing.assert_close(b['role_logits'],a['role_logits'][:,order],rtol=1e-5,atol=1e-6);torch.testing.assert_close(b['router_activation'],a['router_activation'],rtol=1e-5,atol=1e-6)

def test_single_action_edge_is_finite():
 o=CausalEvidenceRouter().eval()(**_x(1,1));assert all(torch.isfinite(o[k]).all() for k in ('action_logits','action_logit_residual','router_activation','role_logits'))
