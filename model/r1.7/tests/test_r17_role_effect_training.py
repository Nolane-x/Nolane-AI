from pathlib import Path
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r17_role_effect_training import role_effect_ranker_trainable_parameter_names, role_effect_internal_gate

def _root(): return Path(__file__).resolve().parents[1]
def _model():
    r=_root(); return load_r17_checkpoint(r/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt',expected_r1_2_checkpoint=r/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=r/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_role_effect_optimizer_scope_is_ranker_only():
    names=role_effect_ranker_trainable_parameter_names(_model()); assert names; assert all(n.startswith('causal_role_effect_ranker.') for n in names)
def test_role_effect_gate_requires_strict_overall_ranking_gain_and_family_preservation():
    good={'candidate_rank_accuracy':0.7,'baseline_rank_accuracy':0.6,'families':{'causal_laws':{'candidate_rank_accuracy':0.6,'baseline_rank_accuracy':0.5},'causal_switch':{'candidate_rank_accuracy':0.8,'baseline_rank_accuracy':0.8}}}; assert role_effect_internal_gate(good); assert not role_effect_internal_gate(dict(good,candidate_rank_accuracy=0.6)); bad=dict(good);bad['families']=dict(good['families']);bad['families']['causal_switch']={'candidate_rank_accuracy':0.7,'baseline_rank_accuracy':0.8};assert not role_effect_internal_gate(bad)
def test_role_effect_collector_and_evaluator_use_aligned_effects_and_tied_best_targets():
    from cogcoder.r17_benchmark import make_r17_task
    from cogcoder.r17_role_effect_training import collect_role_effect_episode,evaluate_role_effect_episodes
    import torch
    model=_model(); ep=collect_role_effect_episode(model,make_r17_task('causal_laws','train',194),exploration_steps=6,max_steps=14); assert ep.steps; row=ep.steps[0]; assert row.need_sketch.shape==(64,); assert row.role_effects.ndim==2 and row.role_effects.shape[1]==64; assert row.target_progress.shape==(row.role_effects.shape[0],); assert row.best_mask.dtype==torch.bool; assert bool(row.best_mask.any()); metrics=evaluate_role_effect_episodes(model,[ep]); assert metrics['rows']>0; assert 0<=metrics['candidate_rank_accuracy']<=1; assert 0<=metrics['baseline_rank_accuracy']<=1
