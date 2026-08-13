from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def find_controller() -> Path:
    for path in (ROOT/'model/r2.0/cogcoder/r20i_causal_discovery.py', ROOT/'cogcoder/r20i_causal_discovery.py'):
        if path.exists():
            return path
    raise FileNotFoundError('R2.0i controller source not found')


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--metadata-only',action='store_true');args=parser.parse_args()
    manifest=load_json(ROOT/'CURRENT_ONE_WEIGHT_R2_0I.json');current=load_json(ROOT/'research/R2_0_CURRENT_BEST.json')
    current_params=current.get('neural_effective_parameters',current.get('effective_parameters'))
    current_sha=current.get('deployment_weight_sha256',current.get('one_weight_sha256'))
    fresh=current.get('fresh') if isinstance(current.get('fresh'),dict) else None
    fresh_rate=fresh.get('candidate_solve_rate') if fresh else current.get('fresh_solve_rate')
    fresh_consumed=fresh.get('consumed') if fresh else current.get('fresh_consumed')
    assert manifest['effective_parameters']==78_779_253
    assert current_params==manifest['effective_parameters']
    assert current_sha==manifest['sha256']
    assert fresh_rate==0.6 and fresh_consumed is True
    assert current.get('status')=='accepted_train_dev_fresh'
    controller=find_controller();controller_sha=sha256(controller);assert controller_sha==manifest['controller_sha256']
    print(json.dumps({'status':'PASS','effective_parameters':manifest['effective_parameters'],'weight_sha256':manifest['sha256'],'controller_sha256':controller_sha,'fresh_solve_rate':fresh_rate,'fresh_consumed':fresh_consumed,'metadata_only':bool(args.metadata_only)},sort_keys=True))


if __name__=='__main__':main()
