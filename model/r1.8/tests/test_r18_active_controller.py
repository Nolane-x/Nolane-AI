from pathlib import Path
import inspect
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_active_controller import run_active_executive_episode
from cogcoder.r18_benchmark import make_r18_task

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ActiveExecutive.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_active_controller_source_does_not_depend_on_oracle():
    import cogcoder.r18_active_controller as module;source=inspect.getsource(module);assert 'oracle_plan' not in source;assert '._goal' not in source and '._regime_maps' not in source and '._action_kinds' not in source
def test_full_and_no_recurrence_closed_loop_execute_public_tasks_within_budget():
    model=_model().eval()
    for mode in ('full','no_recurrence'):
        task=make_r18_task('conditional_regimes','train',300);budget=task.budget_remaining;result=run_active_executive_episode(model,task,mode=mode);assert result['mode']==mode;assert result['steps']<=budget;assert isinstance(result['solved'],bool);assert result['done'] is True;assert result['task_id'].startswith('nolane-figg18-v1:train:')
def test_random_controller_is_deterministic_per_repeat_seed():
    model=_model().eval();a=run_active_executive_episode(model,make_r18_task('regime_switch','train',301),mode='random',random_repeat=2);b=run_active_executive_episode(model,make_r18_task('regime_switch','train',301),mode='random',random_repeat=2);assert a['actions']==b['actions'];assert a['solved']==b['solved']
