import torch
from cogcoder.r18_reliability_training import ReliabilityTrainingRow,calibrate_learned_certificate,learned_certificate_scores,reliability_trainable_parameter_names

def test_learned_certificate_keeps_hard_evidence_gate():
    confidence=torch.tensor([[.99,.99,.8]]); meta=torch.tensor([[[.25,1.,1.],[0.,1.,1.],[.25,.5,1.]]]); score=learned_certificate_scores(confidence,meta); assert torch.allclose(score,torch.tensor([[.99,0.,.4]]),atol=1e-6)
def test_reliability_scope_is_only_existing_confidence_head():
    class Fake:
        def named_parameters(self): return iter([('conditional_law_confidence_head.weight',torch.nn.Parameter(torch.zeros(1,256))),('conditional_law_confidence_head.bias',torch.nn.Parameter(torch.zeros(1))),('conditional_law_effect_head.weight',torch.nn.Parameter(torch.zeros(128,256)))])
    assert reliability_trainable_parameter_names(Fake())==['conditional_law_confidence_head.weight','conditional_law_confidence_head.bias']
def test_learned_certificate_gate_requires_precision_and_coverage_per_family():
    rows=[]
    for family in ('a','b'): rows += [ReliabilityTrainingRow(family,.95,.001),ReliabilityTrainingRow(family,.85,.002),ReliabilityTrainingRow(family,.2,.02),ReliabilityTrainingRow(family,.1,.03)]
    result=calibrate_learned_certificate(rows,thresholds=(.5,.8,.9),acceptable_mse=.005,required_precision=.95,min_coverage=.4,min_family_coverage=.4); assert result.threshold==.8 and result.precision==1.0 and result.coverage==.5 and all(v==.5 for v in result.family_coverage.values())
