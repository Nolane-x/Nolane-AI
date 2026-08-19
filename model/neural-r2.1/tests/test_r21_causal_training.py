from __future__ import annotations
import torch
from cogcoder.r21_causal_training import CausalRouterTargets,causal_router_loss,set_valued_policy_loss
from cogcoder.r21_causal_router import CausalEvidenceRouter

def test_set_valued_supervision_respects_action_symmetry():
 mask=torch.tensor([[True,True,False]]);a=set_valued_policy_loss(torch.tensor([[2.,1.,0.]]),mask);b=set_valued_policy_loss(torch.tensor([[1.,2.,0.]]),mask);torch.testing.assert_close(a,b)

def test_loss_is_finite_and_backpropagates():
 torch.manual_seed(21);m=CausalEvidenceRouter();b,a=2,4;g=torch.Generator().manual_seed(212);x={'state':torch.randn(b,128,generator=g),'context':torch.randn(b,64,generator=g),'action_embeddings':torch.randn(b,a,640,generator=g),'parent_effects':torch.randn(b,a,128,generator=g),'imagined_effects':torch.randn(b,a,128,generator=g),'evidence_effects':torch.randn(b,a,128,generator=g),'action_memory':torch.randn(b,a,7,generator=g),'imagined_uncertainty':torch.rand(b,a,generator=g),'imagined_value':torch.randn(b,a,generator=g),'base_action_logits':torch.randn(b,a,generator=g),'progress':torch.rand(b,1,generator=g),'budget_fraction':torch.rand(b,1,generator=g),'previous_feedback':torch.randn(b,3,generator=g)};t=CausalRouterTargets(torch.tensor([[True,True,True,False],[False,True,False,False]]),torch.tensor([1.,0.]),torch.zeros(b,a,dtype=torch.long),torch.tensor([[False,False,False,True],[False,False,False,False]]));r=causal_router_loss(m(**x),t,base_action_logits=x['base_action_logits']);r['loss'].backward();assert torch.isfinite(r['loss']);assert any(p.grad is not None and torch.isfinite(p.grad).all() and p.grad.abs().sum()>0 for p in m.parameters())
