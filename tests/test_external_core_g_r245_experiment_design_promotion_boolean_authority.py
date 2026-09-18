from __future__ import annotations

import pytest

from nolane.external_core.experiment_design import ExperimentDesignExecutionReceipt


def _canonical_receipt() -> ExperimentDesignExecutionReceipt:
    return ExperimentDesignExecutionReceipt(
        design_id="experiment-design:r245",
        reasoning_hypothesis_id="reasoning:r245",
        verification_plan_id="verification:r245",
        experiment_id="experiment:r245",
        selected_hypothesis_id="hypothesis:r245",
        executed_selection_probe_ids=("probe:selection",),
        verification_probe_ids=("probe:verification",),
        selection_oracle_calls=1,
        verification_oracle_calls=1,
        actual_cost=1.0,
        promoted=False,
    )


@pytest.mark.parametrize("alias", [0, 0.0, "", None])
def test_experiment_design_execution_receipt_rejects_falsey_non_bool_promotion_aliases(
    alias: object,
) -> None:
    with pytest.raises(ValueError, match="promoted.*exact bool"):
        ExperimentDesignExecutionReceipt(
            design_id="experiment-design:r245",
            reasoning_hypothesis_id="reasoning:r245",
            verification_plan_id="verification:r245",
            experiment_id="experiment:r245",
            selected_hypothesis_id="hypothesis:r245",
            executed_selection_probe_ids=("probe:selection",),
            verification_probe_ids=("probe:verification",),
            selection_oracle_calls=1,
            verification_oracle_calls=1,
            actual_cost=1.0,
            promoted=alias,
        )


@pytest.mark.parametrize("alias", [0, 0.0])
def test_experiment_design_execution_restore_rejects_digest_preserving_falsey_aliases(
    alias: object,
) -> None:
    state = _canonical_receipt().to_state()
    state["promoted"] = alias

    with pytest.raises(ValueError, match="promoted.*exact bool"):
        ExperimentDesignExecutionReceipt.from_state(state)


def test_experiment_design_execution_exact_false_round_trips() -> None:
    receipt = _canonical_receipt()

    restored = ExperimentDesignExecutionReceipt.from_state(receipt.to_state())

    assert restored == receipt
    assert restored.promoted is False
