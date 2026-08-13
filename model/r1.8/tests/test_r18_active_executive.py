from pathlib import Path
import torch
from cogcoder.r17_training import load_r17_checkpoint


def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]

def _inputs(model,batch=2,actions=5):
    return dict(state_sketch=torch.randn(batch,128),context_fingerprint=torch.randn(batch,64),progress=torch.rand(batch,1),budget_fraction=torch.rand(batch,1),previous_feedback=torch.randn(batch,3),conditional_hidden=torch.randn(batch,actions,256),control_effect=torch.randn(batch,actions,64),evidence_meta=torch.rand(batch,actions,3),progress_memory=torch.randn(batch,actions,2),recurrent_state=model.init_r18_executive_state(batch_size=batch,device=torch.device('cpu')))

def test_r18_active_executive_shapes_and_parameter_budget():
    model=_model();out=model.r18_executive_step(**_inputs(model));assert out['logits'].shape==(2,5);assert out['state'].shape==(2,256);assert out['action_repr'].shape==(2,5,256);params=sum(p.numel() for n,p in model.named_parameters() if n.startswith('r18_executive_'));assert params==857_857

def test_r18_active_executive_is_action_permutation_equivariant_and_state_invariant_to_permutation():
    torch.manual_seed(18);model=_model().eval();inputs=_inputs(model,batch=1,actions=4);base=model.r18_executive_step(**inputs);perm=torch.tensor([2,0,3,1]);moved=dict(inputs)
    for key in ('conditional_hidden','control_effect','evidence_meta','progress_memory'):moved[key]=inputs[key][:,perm]
    alt=model.r18_executive_step(**moved);assert torch.allclose(alt['logits'],base['logits'][:,perm],atol=1e-6);assert torch.allclose(alt['state'],base['state'],atol=1e-6)

def test_r18_active_executive_recurrent_state_changes_with_public_input():
    model=_model().eval();inputs=_inputs(model,batch=1,actions=4);zero=inputs['recurrent_state'].clone();first=model.r18_executive_step(**inputs);inputs2=dict(inputs);inputs2['recurrent_state']=first['state'];inputs2['progress']=inputs['progress']+.2;second=model.r18_executive_step(**inputs2);assert not torch.allclose(first['state'],zero);assert not torch.allclose(second['state'],first['state'])
