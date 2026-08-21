import torch
from torch import nn
from r23.ultra_core import ScaledRecursiveDistilledReasoner, r22_parameter_count
from r23.gating import HardDelegationWrapper, delegation_targets


def _inputs(batch=2, actions=4):
    return dict(state=torch.randn(batch,128),context=torch.randn(batch,64),action_embeddings=torch.randn(batch,actions,640),parent_effects=torch.randn(batch,actions,128),imagined_effects=torch.randn(batch,actions,128),evidence_effects=torch.randn(batch,actions,128),action_memory=torch.randn(batch,actions,7),imagined_uncertainty=torch.rand(batch,actions),imagined_value=torch.randn(batch,actions),base_action_logits=torch.randn(batch,actions),progress=torch.rand(batch,1),budget_fraction=torch.rand(batch,1),previous_feedback=torch.randn(batch,3),base_stop_logit=torch.zeros(batch),base_success_probability=torch.full((batch,),0.5))


def test_ultra_physical_delta_is_exact_and_under_80m_total():
    model=ScaledRecursiveDistilledReasoner(latent_dim=1344,n_heads=21,ff_mult=2)
    assert r22_parameter_count(model)==50_487_372
    assert 29_370_727+r22_parameter_count(model)==79_858_099
    assert 79_858_099 < 80_000_000


def test_untrained_ultra_core_is_parent_policy_noop():
    torch.manual_seed(1); model=ScaledRecursiveDistilledReasoner(latent_dim=192,n_heads=6,ff_mult=2); x=_inputs(); out=model(**x,reasoning_steps=1)
    assert torch.equal(out['action_logits'],x['base_action_logits'])


def test_weight_sharing_supports_extra_depth_without_extra_parameters():
    model=ScaledRecursiveDistilledReasoner(latent_dim=192,n_heads=6,ff_mult=2); before=r22_parameter_count(model); out=model(**_inputs(batch=1),reasoning_steps=4)
    assert out['action_logits_trajectory'].shape[1]==4
    assert r22_parameter_count(model)==before


def test_delegation_target_requires_actual_repair():
    target=delegation_targets(torch.tensor([False,False,True,True]),torch.tensor([True,False,True,False]),torch.tensor([True,True,False,True]))
    assert target.tolist()==[True,False,False,False]


class Dummy(nn.Module):
    def forward(self, **kw):
        base=kw['base_action_logits']; proposal=base.clone(); proposal[:,0]=-2; proposal[:,1]=3; score=torch.tensor([.95,.2],dtype=base.dtype)
        return {'proposal_action_logits':proposal,'override_gate_logit':torch.logit(score),'action_logits':base}


def test_hard_delegation_preserves_parent_below_threshold():
    base=torch.tensor([[4.,0.],[4.,0.]]); out=HardDelegationWrapper(Dummy(),threshold=.9)(base_action_logits=base,reasoning_steps=1)
    assert out['hard_override'].tolist()==[True,False]
    assert out['action_logits'][0].argmax().item()==1
    assert out['action_logits'][1].argmax().item()==0
