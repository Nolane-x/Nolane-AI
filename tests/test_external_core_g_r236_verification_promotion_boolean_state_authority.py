from __future__ import annotations

import pytest

from nolane.external_core.verification import PromotionReceipt


def _promotion_state() -> dict[str, object]:
    return PromotionReceipt(
        receipt_id="promotion-r236-00000001",
        agent_id="coding.backend.01",
        candidate_version="r236-candidate",
        physical_parameters=90_000_000,
        accepted=True,
        reason="accepted_bounded_candidate",
        evidence_ids=("evidence-r236",),
        promoted=True,
        previous_version="r235-production",
    ).to_state()


def test_r236_promotion_receipt_rejects_truthy_string_for_accepted() -> None:
    state = _promotion_state()
    state["accepted"] = "false"

    with pytest.raises(ValueError, match="promotion accepted must be an exact boolean"):
        PromotionReceipt.from_state(state)


def test_r236_promotion_receipt_rejects_truthy_string_for_promoted() -> None:
    state = _promotion_state()
    state["promoted"] = "false"

    with pytest.raises(ValueError, match="promotion promoted must be an exact boolean"):
        PromotionReceipt.from_state(state)
