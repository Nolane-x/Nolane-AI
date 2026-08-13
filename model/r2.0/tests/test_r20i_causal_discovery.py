from __future__ import annotations

from pathlib import Path

from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r19_standalone import load_r19_standalone
from cogcoder.r20e_training import load_r20e_checkpoint

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'checkpoints/Nolane-R1.9-78M-STRONGEST-ONE-WEIGHT-FP16.pt'
R20E = ROOT / 'checkpoints/Nolane-R2.0e-RIE-EvidenceEffect.pt'

class PublicTaskProxy:
    _allowed = {'observe','render_observation','step','done','solved','task_id','family','action_descriptions'}
    def __init__(self, task): object.__setattr__(self, '_wrapped', task)
    def __getattribute__(self, name):
        if name in {'_wrapped','_allowed','__class__'}: return object.__getattribute__(self, name)
        if name.startswith('_') or name not in object.__getattribute__(self, '_allowed'): raise AssertionError(f'private/non-contract access forbidden: {name}')
        return getattr(object.__getattribute__(self, '_wrapped'), name)

def _models():
    parent, rollout, _ = load_r19_standalone(PARENT); executive, _ = load_r20e_checkpoint(R20E, expected_parent_path=PARENT); return parent, rollout, executive

def test_active_causal_discovery_uses_public_contract_and_solves_probe_set():
    from cogcoder.r20i_causal_discovery import run_public_causal_discovery_episode
    solved=0
    for index in range(1950,1960):
        result=run_public_causal_discovery_episode(PublicTaskProxy(make_r18_task('causal_prerequisites','train',index)));solved+=int(result['solved']);assert result['used_private_fields'] is False;assert result['parameter_count']==0;assert result['steps']<=28
    assert solved==10

def test_hybrid_falls_back_to_exact_r20e_depth1_on_non_prerequisite_family():
    from cogcoder.r20e_controller import run_r20e_episode
    from cogcoder.r20i_causal_discovery import run_r20i_episode
    parent,rollout,executive=_models();a=make_r18_task('conditional_regimes','train',1961);b=make_r18_task('conditional_regimes','train',1961);expected=run_r20e_episode(parent,rollout,executive,a,mode='fixed_depth_1',beam_width=1);actual=run_r20i_episode(parent,rollout,executive,b,mode='hybrid_active_causal',beam_width=1);assert actual['actions']==expected['actions'];assert actual['solved']==expected['solved'];assert actual['controller_path']=='r20e_depth1_fallback'

def test_aux_numeric_signature_ignores_bookkeeping_and_names():
    from cogcoder.r20i_causal_discovery import auxiliary_numeric_signature
    a={'step':1,'budget_remaining':20,'progress_signal':.5,'state':[0,0,0],'target':[1,1,1],'mystery':{'x':2,'y':0}};b={'step':9,'budget_remaining':12,'progress_signal':.7,'state':[3,0,0],'target':[1,1,1],'mystery':{'x':2,'y':0}};assert auxiliary_numeric_signature(a)==auxiliary_numeric_signature(b)
