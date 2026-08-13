from pathlib import Path
import pytest

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_operator_training import (
    collect_operator_transitions,
    operator_executor_internal_gate,
    operator_executor_trainable_parameter_names,
)
from cogcoder.r17_training import load_r17_checkpoint


def _root(): return Path(__file__).resolve().parents[1]
def _model():
    r=_root();return load_r17_checkpoint(r/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt',expected_r1_2_checkpoint=r/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=r/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]


def test_operator_collector_is_train_only_and_emits_five_public_transitions():
    rows=collect_operator_transitions(make_r17_task('composition_holdout','train',282))
    assert len(rows)==5
    assert all(len(row.before)==4 and len(row.after)==4 for row in rows)
    assert len({row.action_description for row in rows})==5
    with pytest.raises(ValueError,match='train split'):
        collect_operator_transitions(make_r17_task('composition_holdout','dev',0))


def test_operator_executor_scope_is_executor_only():
    names=operator_executor_trainable_parameter_names(_model())
    assert names
    assert all(name.startswith('program_executor_') for name in names)
    assert all('action_encoder' not in name for name in names)


def test_operator_gate_requires_exact_element_and_each_operator_threshold():
    good={'exact_vector_accuracy':.99,'element_accuracy':.999,'operators':{'a':{'exact_vector_accuracy':.98},'b':{'exact_vector_accuracy':.96}}}
    assert operator_executor_internal_gate(good)
    assert not operator_executor_internal_gate(dict(good,exact_vector_accuracy=.97))
    bad=dict(good);bad['operators']={'a':{'exact_vector_accuracy':.94},'b':{'exact_vector_accuracy':1.0}}
    assert not operator_executor_internal_gate(bad)


def test_operator_batch_encodes_one_dynamic_action_per_transition_with_action_axis():
    from cogcoder.r17_operator_training import OperatorTransition, _batch_tensors
    model=_model()
    rows=[
        OperatorTransition((0,1,2,3),'rotate vector one cell left',(1,2,3,0)),
        OperatorTransition((1,2,3,4),'add one modulo seven to each value',(2,3,4,5)),
    ]
    before,after,actions=_batch_tensors(model,rows)
    assert before.shape==(2,4)
    assert after.shape==(2,4)
    assert actions.shape==(2,model.workspace_dim)


def test_operator_trainable_snapshot_restore_roundtrip_changes_only_executor():
    import torch
    from cogcoder.r17_operator_training import snapshot_trainable_state, restore_trainable_state
    model=_model(); names=operator_executor_trainable_parameter_names(model)
    parent_name=next(n for n,_ in model.named_parameters() if not n.startswith('program_executor_'))
    parent_before=dict(model.named_parameters())[parent_name].detach().clone()
    snap=snapshot_trainable_state(model,names)
    first=names[0]
    with torch.no_grad(): dict(model.named_parameters())[first].add_(3.0)
    restore_trainable_state(model,snap)
    assert torch.allclose(dict(model.named_parameters())[first],snap[first])
    assert torch.allclose(dict(model.named_parameters())[parent_name],parent_before)
