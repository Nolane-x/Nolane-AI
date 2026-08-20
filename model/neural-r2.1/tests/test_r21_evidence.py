from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_locked_fresh_evidence_is_sha_bound_and_noncausal_preserving():
 lock=json.loads((ROOT/'evidence/R2_1A_PRE_FRESH_LOCK.json').read_text());fresh=json.loads((ROOT/'evidence/R2_1A_FRESH_RESULT.json').read_text());current=json.loads((ROOT/'CURRENT_BEST.json').read_text());assert lock['fresh_evaluation']['status']=='LOCKED_UNCONSUMED';assert lock['delta_sha256']==fresh['delta_sha256']==current['delta_sha256'];assert fresh['weights_modified_after_fresh'] is False;assert fresh['baseline']['solved']==38 and fresh['candidate']['solved']==40 and fresh['gain_pp']==2.5;assert fresh['baseline']['families']['causal_prerequisites']['solved']==2 and fresh['candidate']['families']['causal_prerequisites']['solved']==4
 for fam in ('conditional_regimes','regime_switch','implicit_goal_regimes'):
  assert fresh['baseline']['families'][fam]==fresh['candidate']['families'][fam]
 assert current['fresh']['holdout_consumed'] is True;assert current['experimental_recursive_core']['status']=='architecture_verified_not_weight_admitted'
