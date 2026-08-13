import torch
from cogcoder.r18_controller import CertificateCalibrationRow,calibrate_reliability_threshold,certificate_scores_from_tensors,select_experiment

def test_certificate_requires_evidence_context_consistency_and_model_memory_agreement():
    predicted=torch.tensor([[[1.,0.],[0.,1.],[1.,1.],[0.,0.]]]); evidence=torch.tensor([[[1.,0.],[0.,1.],[-1.,-1.],[0.,0.]]]); meta=torch.tensor([[[.25,1.,1.],[0.,0.,1.],[.25,1.,1.],[.25,.2,1.]]]); score=certificate_scores_from_tensors(predicted,evidence,meta)
    assert score.shape==(1,4) and score[0,0]>.7 and score[0,1]==0 and score[0,2]<.5 and score[0,3]<.3

def test_select_experiment_prefers_unreliable_low_evidence_action_and_is_permutation_equivariant():
    d=['opaque actuator Nox-01','opaque actuator Vela-02','opaque actuator Iri-03','submit current hypothesis']; s=torch.tensor([.9,.0,.4,0.]); c=torch.tensor([2,0,1,0]); chosen=select_experiment(d,s,c); assert chosen==1; perm=[2,0,3,1]; moved=select_experiment([d[i] for i in perm],s[perm],c[perm]); assert perm[moved]==chosen

def test_calibration_maximizes_coverage_subject_to_precision_and_family_non_regression():
    rows=[CertificateCalibrationRow('a',.95,.001),CertificateCalibrationRow('a',.85,.002),CertificateCalibrationRow('a',.65,.020),CertificateCalibrationRow('b',.92,.001),CertificateCalibrationRow('b',.82,.003),CertificateCalibrationRow('b',.60,.030)]; result=calibrate_reliability_threshold(rows,thresholds=(.5,.7,.8,.9),acceptable_mse=.005,required_precision=1.0); assert result.threshold==.8 and result.precision==1.0 and result.coverage==4/6 and set(result.family_precision)=={'a','b'}
