from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cogcoder.kfigg22 import evaluate_kfigg22

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--start',type=int,required=True);p.add_argument('--count',type=int,default=200)
    p.add_argument('--top-k',type=int,default=2);p.add_argument('--max-calls',type=int,default=7)
    p.add_argument('--stale-probability',type=float,default=.04);p.add_argument('--program-probability',type=float,default=.08)
    p.add_argument('--dependency-probability',type=float,default=.60);p.add_argument('--distractors',type=int,default=48)
    p.add_argument('--output')
    a=p.parse_args()
    r=evaluate_kfigg22(seeds=range(a.start,a.start+a.count),top_k=a.top_k,max_calls=a.max_calls,stale_probability=a.stale_probability,distractors=a.distractors,program_probability=a.program_probability,dependency_probability=a.dependency_probability)
    out={k:v for k,v in r.items() if k!='rows'}
    text=json.dumps(out,indent=2,sort_keys=True)+'\n';print(text,end='')
    if a.output: open(a.output,'w').write(text)
if __name__=='__main__':main()
