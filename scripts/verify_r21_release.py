from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from statistics import median
ROOT=Path(__file__).resolve().parents[1]
LOCKED={
 'cogcoder/knowledge_types.py':'ba4ccff2c5d15e1b280e5a64c0ed6a40d1485a137519e3d3911d15803a72bb93',
 'cogcoder/knowledge_store.py':'f4b56bdd3eb3fe4ddc94cf77b765e8f349dc479359bf59d413817d8c5d3f14c0',
 'cogcoder/knowledge_ledger.py':'9202965529f8a89594c9fa7e6ee9994ef3f5ce71332acf037663795851e7d8d8',
 'cogcoder/retrieval_microcycle.py':'3c1e43c7233b7961b2a1abcbdeca93cc273cb891ee3ca79f6507879a652bb3d7',
 'cogcoder/generation_retrieval.py':'1cbf607a62e19acef744d1fb7e4243cb7e3f50f1121a6aa68dc55401a2b6ee12',
 'cogcoder/kfigg21.py':'558e8c7bb940a2b63eabfced1f829e889fba7ee963cbbd0b5267434e4d33b74e'}
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads((ROOT/path).read_text())
def metadata_gate():
    for rel,expected in LOCKED.items():
        actual=sha(ROOT/rel)
        if actual!=expected: raise AssertionError(f'locked source drift {rel}: {actual}')
    current=load('research/R2_1_CURRENT_BEST.json'); fresh=load('research/r2.1/results/r2_1_fresh.json'); consumed=load('research/R2_1_FRESH_CONSUMED.json')
    if current['neural_effective_parameters']!=78_779_253 or current['new_r2_1_neural_parameters']!=0: raise AssertionError('parameter contract mismatch')
    if current['deployment_weight_sha256']!='b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e': raise AssertionError('parent weight drift')
    if not fresh.get('fresh_consumed') or not consumed.get('fresh_consumed'): raise AssertionError('fresh not marked consumed')
    if fresh['cases']!=200 or fresh['retrieve_once_solve_rate']!=0.67 or fresh['interleaved_solve_rate']!=1.0 or fresh['gain_pp']!=33.0 or fresh['provenance_failures']!=0: raise AssertionError('fresh result manifest mismatch')
    return {'locked_files':len(LOCKED),'fresh_cases':fresh['cases'],'new_neural_parameters':0}
def full_gate():
    sys.path.insert(0,str(ROOT)); from cogcoder.kfigg21 import evaluate_kfigg21
    r=evaluate_kfigg21(seeds=range(2000,2200),top_k=1,max_calls=4,distractors=36); rows=r.pop('rows')
    once=[x[1].retrieved_chars for x in rows if x[1].correct]; inter=[x[2].retrieved_chars for x in rows if x[2].correct]
    if (r['retrieve_once_solve_rate'],r['interleaved_solve_rate'],r['gain_pp'],r['provenance_failures'])!=(0.67,1.0,33.0,0): raise AssertionError(f'fresh reproduction mismatch {r}')
    if median(inter)/median(once)!=0.75: raise AssertionError('retrieval character ratio mismatch')
    return {'fresh_replayed':200,'retrieve_once_solved':r['retrieve_once_solved'],'interleaved_solved':r['interleaved_solved'],'gain_pp':r['gain_pp'],'median_chars_ratio':0.75}
def main():
    p=argparse.ArgumentParser();p.add_argument('--metadata-only',action='store_true');a=p.parse_args(); out={'metadata':metadata_gate()}
    if not a.metadata_only: out['retrieval_reproduction']=full_gate()
    print(json.dumps({'status':'PASS',**out},indent=2,sort_keys=True))
if __name__=='__main__': main()
