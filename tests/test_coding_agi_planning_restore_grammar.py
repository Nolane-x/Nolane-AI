from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.planning import PlanNode


def _runtime_state_with_one_plan_revision() -> dict[str, object]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish canonical restore-grammar witness",
        evidence_refs=("ev-plan-restore-grammar",),
        upsert_nodes=(PlanNode("plan-restore-grammar", "Plan restore grammar"),),
    )
    state = runtime.to_state()

    revision = state["planning"]["graph"]["revisions"][0]
    assert revision["version"] == 1
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.planning.graph.version == 1
    return state


def _runtime_state_with_two_plan_revisions() -> dict[str, object]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish first lineage witness",
        evidence_refs=("ev-plan-lineage-1",),
        upsert_nodes=(PlanNode("plan-lineage-a", "Plan lineage A"),),
    )
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish second lineage witness",
        evidence_refs=("ev-plan-lineage-2",),
        upsert_nodes=(PlanNode("plan-lineage-b", "Plan lineage B", dependencies=("plan-lineage-a",)),),
    )
    state = runtime.to_state()

    revisions = state["planning"]["graph"]["revisions"]
    assert revisions[1]["version"] == 2
    assert revisions[1]["parent_version"] == 1
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.planning.graph.version == 2
    return state


def _runtime_state_with_plan_rollback() -> dict[str, object]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish rollback source witness",
        evidence_refs=("ev-plan-rollback-source",),
        upsert_nodes=(PlanNode("plan-rollback-a", "Plan rollback A"),),
    )
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish rollback successor witness",
        evidence_refs=("ev-plan-rollback-successor",),
        upsert_nodes=(PlanNode("plan-rollback-b", "Plan rollback B"),),
    )
    runtime.planning.rollback(
        actor_agent_id="planning.chief",
        source_revision=1,
        reason="restore first canonical plan snapshot",
        evidence_refs=("ev-plan-rollback",),
    )
    state = runtime.to_state()

    revision = state["planning"]["graph"]["revisions"][-1]
    assert revision["version"] == 3
    assert revision["parent_version"] == 2
    assert revision["source_revision"] == 1
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.planning.graph.version == 3
    return state


@pytest.mark.parametrize("malformed_version", (True, "1", 1.0))
def test_master_plan_revision_restore_grammar_rejects_coercible_version_types(
    malformed_version: object,
) -> None:
    state = _runtime_state_with_one_plan_revision()
    state["planning"]["graph"]["revisions"][0]["version"] = malformed_version

    with pytest.raises(ValueError, match="plan revision version must be a positive integer"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("malformed_parent_version", (True, "1", 1.0))
def test_master_plan_revision_restore_grammar_rejects_coercible_parent_version_types(
    malformed_parent_version: object,
) -> None:
    state = _runtime_state_with_two_plan_revisions()
    state["planning"]["graph"]["revisions"][1]["parent_version"] = malformed_parent_version

    with pytest.raises(ValueError, match="plan revision parent version must be a positive integer"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("malformed_source_revision", (True, "1", 1.0))
def test_master_plan_revision_restore_grammar_rejects_coercible_source_revision_types(
    malformed_source_revision: object,
) -> None:
    state = _runtime_state_with_plan_rollback()
    state["planning"]["graph"]["revisions"][-1]["source_revision"] = malformed_source_revision

    with pytest.raises(ValueError, match="plan revision source revision must be a positive integer"):
        OrganizationRuntime.from_state(state)
