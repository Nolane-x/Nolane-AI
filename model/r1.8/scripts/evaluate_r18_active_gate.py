from __future__ import annotations
import argparse,json
from collections import defaultdict
from pathlib import Path
from cogcoder.r17_training import load_r17_checkpoint,sha256_file
from cogcoder.r18_active_controller import run_active_executive_episode
from cogcoder.r18_benchmark import R18_FAMILIES,make_r18_task
START=300;COUNT=20

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('full','no_recurrence','random'),required=True);parser.add_argument('--repeat',type=int,default=0);parser.add_argument('--output',required=True);args=parser.parse_args();root=Path(__file__).resolve().parents[1];r12=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt';r16=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt';checkpoint=root/'checkpoints/Nolane-R1.8-CCSM-ActiveExecutive.pt';model,_=load_r17_checkpoint(checkpoint,expected_r1_2_checkpoint=r12,expected_r1_6_parent_checkpoint=r16);rows=[];families=defaultdict(int);steps=0
    for family in R18_FAMILIES:
        for index in range(START,START+COUNT):
            task=make_r18_task(family,'train',index);result=run_active_executive_episode(model,task,mode=args.mode,random_repeat=args.repeat);rows.append(result);families[family]+=int(result['solved']);steps+=int(result['steps'])
    payload={'version':'r1.8-active-train-gate-v1','mode':args.mode,'repeat':args.repeat,'checkpoint_sha256':sha256_file(checkpoint),'indices':[START,START+COUNT],'tasks':len(rows),'solved':sum(int(row['solved']) for row in rows),'families':dict(sorted(families.items())),'mean_steps':steps/max(1,len(rows)),'rows':rows};path=root/args.output;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in payload.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
