from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path: Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest=json.loads((ROOT/'research/R2_2_CURRENT_BEST.json').read_text())
    assert manifest['status']=='accepted_train_dev_fresh'
    assert manifest['neural_effective_parameters']==78779253
    assert manifest['new_r2_2_neural_parameters']==0
    mapping={
      'workspace':'cogcoder/epistemic_workspace.py',
      'rule_layer':'cogcoder/epistemic_program.py',
      'runtime':'cogcoder/r22_runtime.py',
      'benchmark':'cogcoder/kfigg22.py',
      'evaluator':'scripts/evaluate_r22.py',
    }
    for key,path in mapping.items():
        actual=sha(ROOT/path)
        expected=manifest['source_sha256'][key]
        if actual!=expected: raise AssertionError(f'source drift: {path}: {actual}')
    assert manifest['fresh']['consumed'] is True
    assert manifest['fresh']['integrity_errors']==0
    print(json.dumps({'status':'PASS','source_files':len(mapping),'fresh_gain_pp':manifest['fresh']['gain_pp']},sort_keys=True))
if __name__=='__main__': main()
