from __future__ import annotations
import json
from pathlib import Path
import torch
from cogcoder.r17_training import load_r17_checkpoint,sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES,make_r18_task
from cogcoder.r18_executive_training import collect_executive_episode
FIT_START=200;FIT_COUNT=80;VAL_START=280;VAL_COUNT=20;MAX_STEPS=16

def main():
    torch.set_num_threads(4);root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';parent=root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt';cache=root/'cache/r18_active_executive_cache.pt';manifest=root/'cache/r18_active_executive_cache.json';cache.parent.mkdir(parents=True,exist_ok=True);model,_=load_r17_checkpoint(parent,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16);fit=[collect_executive_episode(model,make_r18_task(f,'train',i),max_steps=MAX_STEPS) for f in R18_FAMILIES for i in range(FIT_START,FIT_START+FIT_COUNT)];val=[collect_executive_episode(model,make_r18_task(f,'train',i),max_steps=MAX_STEPS) for f in R18_FAMILIES for i in range(VAL_START,VAL_START+VAL_COUNT)];meta={'version':'r1.8-active-executive-cache-v1','parent_sha256':sha256_file(parent),'fit_indices':[FIT_START,FIT_START+FIT_COUNT],'val_indices':[VAL_START,VAL_START+VAL_COUNT],'families':list(R18_FAMILIES),'max_steps':MAX_STEPS,'fit_episodes':len(fit),'val_episodes':len(val),'fit_steps':sum(len(e.steps) for e in fit),'val_steps':sum(len(e.steps) for e in val)};torch.save({'metadata':meta,'fit':fit,'val':val},cache);manifest.write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps(meta,sort_keys=True))
if __name__=='__main__':main()
