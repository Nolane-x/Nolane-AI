import json
import torch
from cogcoder.neural_system2 import encode_structured_observation, structured_numeric_delta_sketch, project_causal_role_effects
from cogcoder.r18_control_state import infer_controllable_effect_projection

def _pair(state_key='state',target_key='target'):
    before=json.dumps({state_key:[0,1,2],target_key:[3,3,3],'step':0},sort_keys=True);after=json.dumps({state_key:[1,1,2],target_key:[3,3,3],'step':1},sort_keys=True);return before,after
def _encode(text):
    ids,values=encode_structured_observation(text,max_atoms=96);return ids.unsqueeze(0),values.unsqueeze(0)
def test_controllable_projection_is_schema_rename_invariant_in_role_coordinates():
    role_effects=[]
    for state_key,target_key in [('state','target'),('alpha','omega')]:
        before,after=_pair(state_key,target_key);bi,bv=_encode(before);ai,av=_encode(after);role=infer_controllable_effect_projection(bi,bv,ai,av,role_dim=64,source_dim=128);assert float(role['confidence'][0])==1.0;delta=structured_numeric_delta_sketch(bi,bv,ai,av,sketch_dim=128);role_effects.append(project_causal_role_effects(delta,role['effect_projection']))
    assert torch.allclose(role_effects[0],role_effects[1],atol=1e-6)
def test_controllable_projection_abstains_when_no_or_multiple_vectors_change():
    before=json.dumps({'a':[0,1,2],'b':[3,3,3]},sort_keys=True);nochange=json.dumps({'a':[0,1,2],'b':[3,3,3]},sort_keys=True);multi=json.dumps({'a':[1,1,2],'b':[3,2,3]},sort_keys=True);bi,bv=_encode(before)
    for text in (nochange,multi):
        ai,av=_encode(text);role=infer_controllable_effect_projection(bi,bv,ai,av,role_dim=64,source_dim=128);assert float(role['confidence'][0])==0.0;assert torch.count_nonzero(role['effect_projection'])==0
