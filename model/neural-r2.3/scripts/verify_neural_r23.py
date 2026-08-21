from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
arch=json.loads((ROOT/'ARCHITECTURE.json').read_text())
cur=json.loads((ROOT/'CURRENT_BEST.json').read_text())
audit=json.loads((ROOT/'evidence/R2_3_PARAMETER_AUDIT.json').read_text())
fresh=json.loads((ROOT/'evidence/R2_3_FRESH_RESULT.json').read_text())
assert arch['physical_candidate_parameters']==79_858_099
assert arch['physical_candidate_parameters'] < arch['physical_parameter_ceiling']
assert audit['status']=='PASS' and audit['one_weight_serialized_tensor_elements']==79_858_099
assert cur['delta_sha256']==fresh['delta_sha256']==audit['delta_sha256']
assert cur['one_weight_sha256']==fresh['one_weight_sha256']==audit['one_weight_sha256']
assert fresh['weights_modified_after_fresh'] is False and fresh['threshold_modified_after_fresh'] is False
assert fresh['aggregate']['candidate_solved'] > fresh['aggregate']['baseline_solved']
for before,after in fresh['aggregate']['families'].values(): assert after>=before
assert cur['broad_dev']['candidate_solved'] > cur['broad_dev']['baseline_solved']
for before,after in cur['broad_dev']['families'].values(): assert after>=before
print('Neural R2.3 contracts: PASS')
