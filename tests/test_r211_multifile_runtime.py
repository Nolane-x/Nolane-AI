import os

import pytest

from benchmarks.codeworld.r211_multifile_cases import build_r211_cases
from cogcoder.r211_counterfactual_localizer import CounterfactualLocalizer
from cogcoder.r211_multifile_runtime import run_multifile_repair
from scripts.train_r210_copy_edit_proposer import load_r210_proposer


def test_multifile_runtime_can_localize_propose_and_verify_small_panel():
    checkpoint = os.environ.get('R210_CHECKPOINT')
    if not checkpoint:
        pytest.skip('set R210_CHECKPOINT to exercise R2.11 end-to-end runtime')
    model = load_r210_proposer(checkpoint)
    localizer = CounterfactualLocalizer(model, behavior_weight=0.5, edit_gain_weight=0.0)
    cases = build_r211_cases(seed=31100, count=4, providers=8, offpath=2)
    outcomes = [run_multifile_repair(case, model, localizer=localizer, patch_budget=2) for case in cases]
    assert sum(outcome.success for outcome in outcomes) >= 3
    assert all(outcome.patch_outcome is None or outcome.patch_outcome.evaluations <= 2 for outcome in outcomes)
