from pathlib import Path
import torch
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_executive_training import collect_executive_episode,configure_executive_training,executive_trainable_state,restore_executive_trainable_state,train_executive_epoch

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_resume_snapshot_preserves_continuous_adam_rng(tmp_path):
    episodes=[collect_executive_episode(_model(),make_r18_task('conditional_regimes','train',200+i),max_steps=8) for i in range(2)]
    torch.manual_seed(180818);a=_model();configure_executive_training(a);oa=torch.optim.AdamW([p for p in a.parameters() if p.requires_grad],lr=1e-3,weight_decay=1e-4);train_executive_epoch(a,episodes,oa);train_executive_epoch(a,episodes,oa);final_a=executive_trainable_state(a)
    torch.manual_seed(180818);b=_model();configure_executive_training(b);ob=torch.optim.AdamW([p for p in b.parameters() if p.requires_grad],lr=1e-3,weight_decay=1e-4);train_executive_epoch(b,episodes,ob);path=tmp_path/'resume.pt';torch.save({'weights':executive_trainable_state(b),'optimizer':ob.state_dict(),'rng':torch.get_rng_state()},path)
    c=_model();configure_executive_training(c);oc=torch.optim.AdamW([p for p in c.parameters() if p.requires_grad],lr=1e-3,weight_decay=1e-4);payload=torch.load(path,weights_only=False);restore_executive_trainable_state(c,payload['weights']);oc.load_state_dict(payload['optimizer']);torch.set_rng_state(payload['rng']);train_executive_epoch(c,episodes,oc);final_c=executive_trainable_state(c)
    assert set(final_a)==set(final_c) and all(torch.equal(final_a[n],final_c[n]) for n in final_a)
