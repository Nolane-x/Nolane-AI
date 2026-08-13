from pathlib import Path
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r17_program_training import latent_program_trainable_parameter_names,latent_program_internal_gate

def _root():return Path(__file__).resolve().parents[1]
def _model():
 r=_root();return load_r17_checkpoint(r/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt',expected_r1_2_checkpoint=r/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=r/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_program_optimizer_scope_ranker_only():
 names=latent_program_trainable_parameter_names(_model());assert names;assert all(n.startswith('latent_program_ranker.') for n in names)
def test_program_gate_requires_operation_and_submit_gain_with_template_preservation():
 good={'candidate_operation_accuracy':.8,'baseline_operation_accuracy':.5,'candidate_submit_accuracy':.9,'baseline_submit_accuracy':.8,'templates':{'6':{'candidate_operation_accuracy':.8,'baseline_operation_accuracy':.5},'7':{'candidate_operation_accuracy':.75,'baseline_operation_accuracy':.6}}};assert latent_program_internal_gate(good);bad=dict(good,candidate_submit_accuracy=.7);assert not latent_program_internal_gate(bad)

def test_program_metrics_compare_standalone_ranker_to_parent_by_operation_submit_and_template():
    import torch
    from cogcoder.r17_program_training import ProgramTrainingRow, evaluate_program_rows
    model=_model()
    rows=[
        ProgramTrainingRow(template_id=6,program_step=0.0,base_logits=torch.tensor([0.,3.,0.]),policy_features=torch.zeros(3,384),label=1,is_submit=False),
        ProgramTrainingRow(template_id=6,program_step=1.0,base_logits=torch.tensor([0.,0.,3.]),policy_features=torch.zeros(3,384),label=2,is_submit=True),
        ProgramTrainingRow(template_id=7,program_step=0.0,base_logits=torch.tensor([3.,0.,0.]),policy_features=torch.zeros(3,384),label=0,is_submit=False),
    ]
    metrics=evaluate_program_rows(model,rows)
    assert metrics['baseline_operation_accuracy']==1.0
    assert metrics['baseline_submit_accuracy']==1.0
    assert metrics['candidate_operation_accuracy']==0.5
    assert metrics['candidate_submit_accuracy']==0.0
    assert set(metrics['templates'])=={'6','7'}
    assert metrics['templates']['6']['baseline_operation_accuracy']==1.0
    assert metrics['templates']['7']['baseline_operation_accuracy']==1.0

def test_program_training_row_keeps_template_phase_and_submit_metadata():
    import torch
    from cogcoder.r17_program_training import ProgramTrainingRow
    row=ProgramTrainingRow(template_id=7,program_step=2.0,base_logits=torch.zeros(5),policy_features=torch.zeros(5,384),label=4,is_submit=True)
    assert row.template_id==7
    assert row.program_step==2.0
    assert row.is_submit is True
    assert row.policy_features.shape==(5,384)

def test_program_row_conversion_preserves_episode_template_phase_and_submit_alignment():
    from types import SimpleNamespace
    import torch
    from cogcoder.r17_program_training import build_program_rows
    ep0=SimpleNamespace(steps=[SimpleNamespace(label=1,descriptions=('a','op','submit')),SimpleNamespace(label=2,descriptions=('a','op','submit'))])
    ep1=SimpleNamespace(steps=[SimpleNamespace(label=0,descriptions=('op','b','submit'))])
    cached=[
        SimpleNamespace(base_logits=torch.tensor([0.,1.,0.]),policy_features=torch.zeros(3,384),label=1),
        SimpleNamespace(base_logits=torch.tensor([0.,0.,1.]),policy_features=torch.zeros(3,384),label=2),
        SimpleNamespace(base_logits=torch.tensor([1.,0.,0.]),policy_features=torch.zeros(3,384),label=0),
    ]
    rows=build_program_rows([ep0,ep1],cached,[6,7])
    assert [(r.template_id,r.program_step,r.label,r.is_submit) for r in rows]==[(6,0.0,1,False),(6,1.0,2,True),(7,0.0,0,False)]
