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
