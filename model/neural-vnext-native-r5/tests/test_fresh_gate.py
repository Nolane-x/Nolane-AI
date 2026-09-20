from __future__ import annotations

import json
from pathlib import Path

from evaluate_fresh import FRESH_START, FRESH_END, FRESH_EPISODES, LOCKED_GATE


def test_r5_pre_fresh_lock_keeps_new_block_unopened() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "PRE_FRESH_LOCK.json").read_text())
    assert lock["status"] == "FROZEN_FRESH_UNOPENED"
    assert lock["fresh_court"]["opened"] is False
    assert lock["fresh_court"]["index_start"] == FRESH_START == 160
    assert lock["fresh_court"]["index_end"] == FRESH_END == 199
    assert lock["fresh_court"]["episodes_expected"] == FRESH_EPISODES == 160
    assert lock["promotion_gate"] == LOCKED_GATE
    assert lock["frozen_candidate"]["fresh_opened"] is False


def test_r5_reproduction_claim_is_workflow_level_only() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "PRE_FRESH_LOCK.json").read_text())
    reproduction = lock["source_training_reproducibility"]
    assert reproduction["status"] == "BITWISE_REPRODUCED_WORKFLOW_LEVEL"
    assert reproduction["exact_inner_files_reproduced"] is True
    assert reproduction["cross_host_guarantee_claimed"] is False
    assert len(reproduction["observed_workflow_runs"]) == 2
