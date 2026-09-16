from __future__ import annotations

import pytest

from nolane.external_core.debug_evidence import ReproductionReceipt


def _reproduction_state() -> dict[str, object]:
    return ReproductionReceipt(
        receipt_id="repro-r235-00000001",
        sequence=1,
        case_id="case-r235",
        reproducer_agent_id="debugging.reproducer.01",
        deterministic=True,
        minimized=True,
        environment_digest="env-r235",
        failure_fingerprint="failure-r235",
        artifact_refs=("artifact-r235",),
        evidence_refs=("evidence-r235",),
    ).to_state()


def test_r235_reproduction_receipt_rejects_truthy_string_for_deterministic() -> None:
    state = _reproduction_state()
    state["deterministic"] = "false"

    with pytest.raises(ValueError, match="reproduction deterministic must be an exact boolean"):
        ReproductionReceipt.from_state(state)


def test_r235_reproduction_receipt_rejects_truthy_string_for_minimized() -> None:
    state = _reproduction_state()
    state["minimized"] = "false"

    with pytest.raises(ValueError, match="reproduction minimized must be an exact boolean"):
        ReproductionReceipt.from_state(state)
