from __future__ import annotations

import json
from pathlib import Path
import torch
from cogcoder.r17_training import load_r17_checkpoint,sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES,make_r18_task
from cogcoder.r18_controller import CertificateCalibrationRow,calibrate_reliability_threshold,certificate_scores_from_tensors
from cogcoder.r18_training import collect_conditional_law_episode
START=32;COUNT=16;THRESHOLDS=(0.5,0.6,0.7,0.8,0.9);ACCEPTABLE_MSE=0.005;REQUIRED_PRECISION=0.95

def main():
    torch.set_num_threads(4); root=Path(__file__).resolve().parents[1]; r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'; r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'; checkpoint=root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt'; model,meta=load_r17_checkpoint(checkpoint,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16); model.eval(); rows=[]; episodes=0
    with torch.no_grad():
        for family in R18_FAMILIES:
            for index in range(START,START+COUNT):
                episode=collect_conditional_law_episode(model,make_r18_task(family,'train',index),exploration_steps=6,max_steps=16); episodes+=1
                for step in episode.steps:
                    out=model.conditional_law_scores(step.state_sketch.unsqueeze(0),step.context_fingerprint.unsqueeze(0),step.action_embeddings.unsqueeze(0),step.evidence_effects.unsqueeze(0),step.evidence_meta.unsqueeze(0)); score=certificate_scores_from_tensors(out['predicted_effect'],step.evidence_effects.unsqueeze(0),step.evidence_meta.unsqueeze(0))[0]
                    for action_index in torch.nonzero(step.predict_mask,as_tuple=False).flatten().tolist():
                        mse=float((out['predicted_effect'][0,action_index]-step.target_effects[action_index]).pow(2).mean().item()); rows.append(CertificateCalibrationRow(family,float(score[action_index].item()),mse))
    result=calibrate_reliability_threshold(rows,thresholds=THRESHOLDS,acceptable_mse=ACCEPTABLE_MSE,required_precision=REQUIRED_PRECISION); payload={'version':'r1.8-reliability-calibration-v1','checkpoint_sha256':sha256_file(checkpoint),'checkpoint_effective_parameters':meta['candidate_effective_parameters'],'protocol':{'train_indices':[START,START+COUNT],'families':list(R18_FAMILIES),'thresholds':list(THRESHOLDS),'acceptable_mse':ACCEPTABLE_MSE,'required_precision':REQUIRED_PRECISION},'episodes':episodes,'rows':len(rows),'selected_threshold':result.threshold,'precision':result.precision,'coverage':result.coverage,'selected':result.selected,'total':result.total,'family_precision':result.family_precision}; path=root/'results/r1_8_reliability_calibration.json'; path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); print(json.dumps(payload,sort_keys=True))
if __name__=='__main__': main()
