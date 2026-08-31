from nolane.external_core import _goal_design_base as base
from nolane.external_core.goal_design import (
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalSpec,
)
from nolane.external_core.goal_design_authenticity import verify_decision_receipt


def test_v2_receipt_identity_matches_pre_truth_base_exactly():
    vector = GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")

    old_plane = base.GoalDesignCoherencePlane()
    old_snapshot = old_plane.freeze_snapshot(vector)
    old = old_plane.admit_decision(
        goal=base.GoalSpec("goal:compat", "Preserve historical authority identity"),
        scenarios=(base.DesignScenario("base"),),
        options=(base.DesignOption("option:compat", "compat", {"base": 0.8}, {}),),
        selected_option_id="option:compat",
        snapshot=old_snapshot,
        current_vector=vector,
    )

    new_plane = GoalDesignCoherencePlane()
    new_snapshot = new_plane.freeze_snapshot(vector)
    new = new_plane.admit_decision(
        goal=GoalSpec("goal:compat", "Preserve historical authority identity"),
        scenarios=(DesignScenario("base"),),
        options=(DesignOption("option:compat", "compat", {"base": 0.8}, {}),),
        selected_option_id="option:compat",
        snapshot=new_snapshot,
        current_vector=vector,
    )

    assert verify_decision_receipt(new) == "v2"
    assert new.receipt_id == old.receipt_id
    assert new.goal_digest == old.goal_digest
    assert new.option_set_digest == old.option_set_digest
    assert new.evaluation_digest == old.evaluation_digest
    assert new.input_manifest_digest == old.input_manifest_digest
