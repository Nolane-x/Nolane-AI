import pytest

from nolane.external_core.goal_design import (
    CoherenceError,
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalSpec,
)


def test_costly_decision_cannot_cross_gate_with_decorative_adversarial_tag_only():
    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r:1", "p:1", "a:1", "i:1", "c:1")
    snapshot = plane.freeze_snapshot(vector)
    scenarios = (
        DesignScenario("base", probability=0.8),
        DesignScenario("break", probability=0.2, tags=("adversarial",)),
    )
    options = (
        DesignOption(
            "costly",
            "Expensive migration with nominal rollback",
            {"base": 0.90, "break": 0.55},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "safe",
            "Keep the reversible path",
            {"base": 0.82, "break": 0.72},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:safe",
        ),
    )

    with pytest.raises(CoherenceError, match="stress"):
        plane.admit_decision(
            goal=GoalSpec("goal:stress-red", "Reject decorative stress tags"),
            scenarios=scenarios,
            options=options,
            selected_option_id="costly",
            snapshot=snapshot,
            current_vector=vector,
        )
