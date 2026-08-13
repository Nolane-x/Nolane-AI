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
