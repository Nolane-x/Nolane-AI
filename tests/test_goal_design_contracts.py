from nolane.external_core.goal_design import GoalDesignCoherencePlane, PlaneState
from nolane.external_core.goal_design_contracts import (
    ArchitectureState,
    ContextState,
    GoalDesignStateBundle,
    IntegrationState,
    PlanningState,
    RequirementsState,
)


def _bundle(snapshot_digest="snap"):
    return GoalDesignStateBundle(
        requirements=RequirementsState(PlaneState("r3", "dr"), ("req:1", "req:2")),
        planning=PlanningState(PlaneState("p4", "dp"), ("req:1", "req:2"), ("cmp:a",)),
        architecture=ArchitectureState(PlaneState("a2", "da"), ("cmp:a",), ("if:a",), ("inv:a",)),
        integration=IntegrationState(PlaneState("i8", "di"), ("cmp:a",), snapshot_digest, ("rb:1",)),
        context=ContextState(PlaneState("c5", "dc"), ("cmp:a",), snapshot_digest),
    )


def test_bundle_binds_all_five_authority_states_into_one_version_vector():
    tokens = _bundle().version_vector.tokens()
    assert tokens == {
        "requirements": "r3@dr", "planning": "p4@dp", "architecture": "a2@da",
        "integration": "i8@di", "context": "c5@dc",
    }


def test_bundle_coherence_is_green_when_traceability_and_snapshot_binding_match():
    report = _bundle().coherence_report(GoalDesignCoherencePlane(), expected_snapshot_digest="snap")
    assert report.coherent


def test_bundle_blocks_integration_and_context_compiled_against_old_snapshot():
    report = _bundle("old").coherence_report(GoalDesignCoherencePlane(), expected_snapshot_digest="new")
    codes = {issue.code for issue in report.issues if issue.blocking}
    assert codes == {"INTEGRATION_SNAPSHOT_MISMATCH", "CONTEXT_SNAPSHOT_MISMATCH"}
