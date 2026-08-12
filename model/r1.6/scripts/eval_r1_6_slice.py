from __future__ import annotations
import argparse, copy, json
from collections import defaultdict
from pathlib import Path
import torch
from cogcoder.edit_training import load_stage2_checkpoint
from cogcoder.frontier_interactive import FAMILIES, build_split
from cogcoder.neural_system2 import encode_action_descriptions, encode_public_observation, encode_structured_observation
from cogcoder.neural_system2_curriculum import FrozenStage2ObservationEncoder
from cogcoder.neural_system2_training import load_system2_checkpoint


def select_tasks(split: str, start: int, count: int):
    pool=build_split(split,per_family=start+count); by=defaultdict(list)
    for task in pool: by[task.family].append(task)
    return [copy.deepcopy(by[f][i]) for f in FAMILIES for i in range(start,start+count)]


def build_arg_parser():
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint',required=True)
    ap.add_argument('--split',choices=('dev','fresh'),default='dev')
    ap.add_argument('--start',type=int,required=True)
    ap.add_argument('--count',type=int,default=6)
    ap.add_argument('--refinement',type=int,default=1)
    ap.add_argument('--output',required=True)
    return ap

def main():
    args=build_arg_parser().parse_args(); root=Path(__file__).resolve().parents[1]
    trunk,tok,_=load_stage2_checkpoint(root/'checkpoints/Nolane-48M-Stage2-Policy.pt'); enc=FrozenStage2ObservationEncoder(trunk,tok,max_length=96)
    model,_=load_system2_checkpoint(root/args.checkpoint,expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'); model.eval()
    rows=[]
    for task in select_tasks(args.split,args.start,args.count):
        state=None; prev=None; fb=None; steps=0; trace=[]
        while not task.done:
            text=task.render_observation(); latent=enc.encode_observation(task.observe()).unsqueeze(0)
            at=encode_action_descriptions(task.action_descriptions,max_bytes=48).unsqueeze(0)
            ot=encode_public_observation(text,max_bytes=384).unsqueeze(0)
            ids,vals=encode_structured_observation(text,max_atoms=64)
            with torch.no_grad():
                out=model(latent,at,state=state,observation_tokens=ot,structured_ids=ids.unsqueeze(0),structured_values=vals.unsqueeze(0),previous_action=prev,previous_feedback=fb,refinement_steps=args.refinement,policy_mode='full')
            state=out.state; action=int(out.action_logits.argmax(-1).item()); result=task.step(action); steps+=1
            trace.append({'action':action,'description':task.action_descriptions[action],'failed':bool(result.failed),'done':bool(result.done),'solved':bool(result.solved)})
            prev=action; fb=(float(result.progress_delta),float(result.information_gain),float(result.failed))
        rows.append({'task_id':task.task_id,'family':task.family,'solved':bool(task.solved),'steps':steps,'trace':trace})
        print({'task':task.task_id,'family':task.family,'solved':bool(task.solved),'steps':steps},flush=True)
    fam={}
    for f in FAMILIES:
        rs=[r for r in rows if r['family']==f]; fam[f]={'solved':sum(int(r['solved']) for r in rs),'total':len(rs),'mean_steps':sum(r['steps'] for r in rs)/len(rs)}
    summary={'checkpoint':args.checkpoint,'slice':f'{args.split}[{args.start}:{args.start+args.count}]','solved':sum(int(r['solved']) for r in rows),'total':len(rows),'mean_steps':sum(r['steps'] for r in rows)/len(rows),'families':fam}
    path=root/args.output; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps({'summary':summary,'rows':rows},indent=2)); print('SUMMARY',json.dumps(summary,sort_keys=True),flush=True)

if __name__=='__main__': main()
