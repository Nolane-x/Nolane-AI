from __future__ import annotations
import torch
from cogcoder.r20_executive import RecursiveImaginationExecutive,r20_parameter_count

def _inputs(batch=3,actions=5):
    g=torch.Generator().manual_seed(2020); return {'state':torch.randn(batch,128,generator=g),'context':torch.randn(batch,64,generator=g),'action_embeddings':torch.randn(batch,actions,640,generator=g),'parent_effects':torch.randn(batch,actions,128,generator=g),'imagined_effects':torch.randn(batch,actions,128,generator=g),'imagined_uncertainty':torch.rand(batch,actions,generator=g),'imagined_value':torch.randn(batch,actions,generator=g),'progress':torch.randn(batch,1,generator=g),'budget_fraction':torch.rand(batch,1,generator=g),'previous_feedback':torch.randn(batch,3,generator=g)}

def test_r20_executive_shapes_probabilities_and_budget():
    torch.manual_seed(20); m=RecursiveImaginationExecutive(); x=_inputs(); out=m(recurrent_state=m.init_state(batch_size=3),**x); assert out['action_logits'].shape==(3,5); assert out['next_state'].shape==(3,m.hidden_dim); assert out['stop_logit'].shape==(3,); assert out['success_probability'].shape==(3,); assert out['depth_logits'].shape==(3,5); assert r20_parameter_count(m)<=700000; assert ((0<=out['success_probability'])&(out['success_probability']<=1)).all()

def test_r20_executive_action_permutation_equivariance():
    torch.manual_seed(20); m=RecursiveImaginationExecutive(); x=_inputs(2,6); s=m.init_state(batch_size=2); a=m(recurrent_state=s,**x); order=torch.tensor([4,0,5,2,1,3]); y=dict(x)
    for key in ('action_embeddings','parent_effects','imagined_effects','imagined_uncertainty','imagined_value'): y[key]=x[key][:,order]
    b=m(recurrent_state=s,**y); torch.testing.assert_close(b['action_logits'],a['action_logits'][:,order],rtol=1e-5,atol=1e-6); torch.testing.assert_close(b['next_state'],a['next_state'],rtol=1e-5,atol=1e-6)

def test_r20_executive_recurrent_state_changes_next_decision():
    torch.manual_seed(20); m=RecursiveImaginationExecutive(); x=_inputs(1,4); z=m.init_state(batch_size=1); a=m(recurrent_state=z,**x); b=m(recurrent_state=a['next_state'],**x); assert not torch.allclose(a['next_state'],b['next_state']); assert not torch.allclose(a['action_logits'],b['action_logits'])
